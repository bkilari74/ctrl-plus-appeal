"""
Ctrl+Appeal — Denial Classification Agent
===========================================
LangGraph coded agent deployed via UiPath Agent Builder.
Runs Claude Haiku via UiPath's Bedrock wrapper.

Pattern: prepare -> react_agent -> postprocess

Responsibility boundary:
  This agent READS a denial record from Data Fabric and CLASSIFIES it
  into one of five routes. It does NOT write results back to Data Fabric --
  persistence is handled by a downstream Maestro activity for reliability
  (write-decoupling pattern).

Input:  record_id (str)
Output: {
    "record_id": str,
    "denial_classification": str,   # one of the 5 routes below
    "requires_human": bool,
    "confidence": float
}
"""

from __future__ import annotations
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

# ──────────────────────────────────────────────────────────────────
# UiPath Data Fabric client + Bedrock-wrapped Claude Haiku client
# These are provided by the UiPath Agent Builder runtime — imported
# here as thin wrappers for local testing / Claude Code development.
# ──────────────────────────────────────────────────────────────────
from data_fabric_client import get_entity_record_by_id
from bedrock_client import invoke_claude_haiku


# ──────────────────────────────────────────────────────────────────
# Deterministic CARC -> route table
# Mirrors the exclusive gateway branches in the Maestro BPMN
# ("Determine Denial Type?").
# ──────────────────────────────────────────────────────────────────
CARC_ROUTE_TABLE = {
    # Medical Necessity
    "CO-50":  "medical_necessity",
    "CO-151": "medical_necessity",

    # Eligibility
    "CO-27":  "eligibility",
    "CO-31":  "eligibility",

    # Coding Error
    "CO-4":   "coding_error",
    "CO-11":  "coding_error",

    # Duplicate Claim
    "CO-18":  "duplicate",

    # Timely Filing
    "CO-29":  "timely_filing",
}

# Routes that always require human sign-off regardless of agent confidence.
# medical_necessity is non-negotiable per California SB 1120
# (Physicians Make Decisions Act) -- a licensed clinician, not an
# algorithm, must make the final determination.
ALWAYS_HUMAN_ROUTES = {"medical_necessity"}

# Confidence floor below which any classification is escalated to a human,
# even if the CARC mapping was deterministic.
CONFIDENCE_FLOOR = 0.70

# Default route + flag for unmapped or conflicting CARC codes.
DEFAULT_ROUTE = "eligibility"


# ──────────────────────────────────────────────────────────────────
# LangGraph state definition
# ──────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    record_id: str
    carc_code: Optional[str]
    rarc_code: Optional[str]
    date_of_service: Optional[str]
    billed_amount: Optional[float]
    denied_amount: Optional[float]
    paid_amount: Optional[float]
    payer_id: Optional[str]
    claim_id: Optional[str]

    # populated during the graph run
    candidate_route: Optional[str]
    confidence: float
    reasoning: Optional[str]

    # final output
    denial_classification: Optional[str]
    requires_human: bool


# ──────────────────────────────────────────────────────────────────
# Node 1 — prepare
# Reads the denial record from Data Fabric (IngestionData entity).
# ──────────────────────────────────────────────────────────────────
def prepare(state: AgentState) -> AgentState:
    record = get_entity_record_by_id("IngestionData", state["record_id"])

    state["carc_code"] = record.get("carc_code")
    state["rarc_code"] = record.get("rarc_code")
    state["date_of_service"] = record.get("date_of_service")
    state["billed_amount"] = record.get("billed_amount")
    state["denied_amount"] = record.get("denied_amount")
    state["paid_amount"] = record.get("paid_amount")
    state["payer_id"] = record.get("payer_id")
    state["claim_id"] = record.get("claim_id")

    return state


# ──────────────────────────────────────────────────────────────────
# Node 2 — react_agent
# Deterministic CARC lookup first. Falls back to a ReAct-style call to
# Claude Haiku (via UiPath's Bedrock wrapper) only when the CARC code is
# missing, unmapped, or conflicting with the RARC code -- e.g. partial
# denials where billed_amount != denied_amount + paid_amount, which can
# indicate a coding or eligibility nuance the static table won't catch.
# ──────────────────────────────────────────────────────────────────
def react_agent(state: AgentState) -> AgentState:
    carc = state.get("carc_code")

    # --- Deterministic path -----------------------------------------
    if carc in CARC_ROUTE_TABLE:
        route = CARC_ROUTE_TABLE[carc]

        # Partial-denial detection: if amounts don't reconcile, treat
        # confidence as lower and let the LLM sanity-check the RARC.
        billed = state.get("billed_amount") or 0
        denied = state.get("denied_amount") or 0
        paid = state.get("paid_amount") or 0
        amounts_reconcile = abs(billed - (denied + paid)) < 0.01

        if amounts_reconcile:
            state["candidate_route"] = route
            state["confidence"] = 0.95
            state["reasoning"] = f"Deterministic CARC match: {carc} -> {route}"
            return state
        else:
            # Amounts don't reconcile -- escalate to ReAct reasoning
            # to confirm the route given RARC context before finalizing.
            state["candidate_route"] = route
            state["confidence"] = 0.55
            state["reasoning"] = (
                f"CARC {carc} maps to {route}, but billed/denied/paid "
                f"amounts do not reconcile (partial denial suspected). "
                f"Escalating to LLM for RARC-informed confirmation."
            )
            return _react_confirm(state)

    # --- Unknown / conflicting CARC -- LLM-assisted fallback ---------
    return _react_confirm(state)


def _react_confirm(state: AgentState) -> AgentState:
    """
    ReAct-style call to Claude Haiku via UiPath's Bedrock wrapper.
    Used only for ambiguous cases -- the model is given the CARC, RARC,
    and claim amounts and asked to pick the best-fit route from the
    fixed list of five, or flag it as unresolvable.
    """
    prompt = f"""You are classifying a healthcare claim denial into exactly
one of these five routes: medical_necessity, eligibility, coding_error,
duplicate, timely_filing.

CARC code: {state.get('carc_code')}
RARC code: {state.get('rarc_code')}
Billed amount: {state.get('billed_amount')}
Denied amount: {state.get('denied_amount')}
Paid amount: {state.get('paid_amount')}
Date of service: {state.get('date_of_service')}

Candidate route from static table (if any): {state.get('candidate_route')}

Respond with a JSON object: {{"route": "<one_of_the_five>", "confidence": <0-1 float>, "reasoning": "<one sentence>"}}
If you cannot confidently resolve this, set route to "eligibility" and confidence below 0.70.
"""

    response = invoke_claude_haiku(prompt)

    state["candidate_route"] = response.get("route", DEFAULT_ROUTE)
    state["confidence"] = float(response.get("confidence", 0.0))
    state["reasoning"] = response.get("reasoning", "LLM fallback classification")

    return state


# ──────────────────────────────────────────────────────────────────
# Node 3 — postprocess
# Applies guardrails and produces the final output. Does NOT write to
# Data Fabric -- that happens in the downstream Maestro activity.
# ──────────────────────────────────────────────────────────────────
def postprocess(state: AgentState) -> AgentState:
    route = state.get("candidate_route")
    confidence = state.get("confidence", 0.0)

    # Guardrail 1: unmapped / unresolved route -> safe default + human
    valid_routes = {"medical_necessity", "eligibility", "coding_error",
                     "duplicate", "timely_filing"}
    if route not in valid_routes:
        route = DEFAULT_ROUTE
        requires_human = True
    # Guardrail 2: medical_necessity is always human (SB 1120)
    elif route in ALWAYS_HUMAN_ROUTES:
        requires_human = True
    # Guardrail 3: confidence floor
    elif confidence < CONFIDENCE_FLOOR:
        requires_human = True
    else:
        requires_human = False

    state["denial_classification"] = route
    state["requires_human"] = requires_human

    return state


# ──────────────────────────────────────────────────────────────────
# Graph assembly
# ──────────────────────────────────────────────────────────────────
def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("prepare", prepare)
    graph.add_node("react_agent", react_agent)
    graph.add_node("postprocess", postprocess)

    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "react_agent")
    graph.add_edge("react_agent", "postprocess")
    graph.add_edge("postprocess", END)

    return graph.compile()


# ──────────────────────────────────────────────────────────────────
# Agent Builder entry point
# ──────────────────────────────────────────────────────────────────
def run(record_id: str) -> dict:
    """
    Entry point invoked by UiPath Agent Builder.

    Args:
        record_id: the IngestionData record to classify

    Returns:
        dict with record_id, denial_classification, requires_human
    """
    app = build_graph()
    initial_state: AgentState = {
        "record_id": record_id,
        "carc_code": None,
        "rarc_code": None,
        "date_of_service": None,
        "billed_amount": None,
        "denied_amount": None,
        "paid_amount": None,
        "payer_id": None,
        "claim_id": None,
        "candidate_route": None,
        "confidence": 0.0,
        "reasoning": None,
        "denial_classification": None,
        "requires_human": False,
    }

    final_state = app.invoke(initial_state)

    return {
        "record_id": final_state["record_id"],
        "denial_classification": final_state["denial_classification"],
        "requires_human": final_state["requires_human"],
    }


if __name__ == "__main__":
    # Local smoke test (requires mock data_fabric_client / bedrock_client)
    import sys
    test_record_id = sys.argv[1] if len(sys.argv) > 1 else "REC-0001"
    result = run(test_record_id)
    print(result)
