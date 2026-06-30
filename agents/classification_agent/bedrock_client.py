"""
Thin wrapper around UiPath's Bedrock-hosted Claude Haiku integration.

In production (deployed via Agent Builder), this resolves to UiPath's
native Bedrock wrapper, configured at the tenant level. This stub exists
for local development/testing with Claude Code -- it returns a
conservative low-confidence fallback rather than calling a live model,
so the agent's guardrail logic (confidence floor -> escalate to human)
can be exercised without network access.

Swap for the real call when deployed:

    from uipath.bedrock import BedrockClient
    client = BedrockClient(model="anthropic.claude-haiku")
    return client.invoke(prompt)
"""

import json
import re


def invoke_claude_haiku(prompt: str) -> dict:
    """
    Local stub. Returns a safe low-confidence fallback so unresolved
    cases route to human review by design, rather than guessing.

    Replace this function body with a real Bedrock invocation in the
    UiPath Agent Builder deployment.
    """
    # Attempt a naive heuristic just so local testing has some signal --
    # this is NOT a substitute for the real LLM call.
    carc_hint = re.search(r"CARC code:\s*(\S+)", prompt)
    carc = carc_hint.group(1) if carc_hint else None

    fallback_map = {
        "CO-50": "medical_necessity",
        "CO-151": "medical_necessity",
        "CO-27": "eligibility",
        "CO-31": "eligibility",
        "CO-4": "coding_error",
        "CO-11": "coding_error",
        "CO-18": "duplicate",
        "CO-29": "timely_filing",
    }

    route = fallback_map.get(carc, "eligibility")
    confidence = 0.5 if carc in fallback_map else 0.3

    return {
        "route": route,
        "confidence": confidence,
        "reasoning": "Local stub fallback (no live Bedrock call) -- replace before deployment.",
    }
