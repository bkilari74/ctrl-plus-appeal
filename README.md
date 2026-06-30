# Ctrl+Appeal — Intelligent Denial Management & Appeals Automation

## Project Description

Ctrl+Appeal is a provider-side, agentic denial management and appeals automation system built entirely on UiPath Cloud. It ingests healthcare claim denials from 835 EDI files, classifies each into one of five denial routes using a LangGraph classification agent, handles each route end-to-end through dedicated Maestro BPMN subprocesses, and keeps a licensed physician in the loop for every medical-necessity determination — satisfying California SB 1120 by construction.

**The problem it solves:** US hospitals receive $260–300B in claim denials annually. ~65% are never appealed — not because appeals fail (3:1 ROI), but because the manual process (45–60 min/appeal) exhausts bandwidth before timely-filing deadlines pass. Ctrl+Appeal eliminates that bottleneck while preserving physician authority over clinical decisions.

## Team

| Name | Role |
|---|---|
| Shweta Chandra | Automation Architect |
| Sumit Paithankar | Automation Developer |
| Bharath Kilari | Automation Developer |
| Lokesh Raj | Automation Developer |

## UiPath Components

| Component | Usage |
|---|---|
| **Maestro BPMN** | Exclusive gateway routing denials into 5 subprocess branches; orchestrates the full ingestion-to-resolution flow |
| **Agent Builder** | Hosts the Classification Agent (LangGraph/coded) and the Appeal Letter Generation Agent |
| **Data Fabric** | `IngestionData` entity — work queue for denial records, written by RPA ingestion, read by the classification agent, updated by every downstream Maestro activity |
| **Action Center / Action Apps** | Human touchpoints: Action App for CPT code correction, Action App for DOS/eligibility verification, Action App for appeal letter editing, and Action Center physician attestation (SB 1120 gate) |
| **Studio Web** | All process logic, Data Fabric R/W, RPA file ingestion — zero desktop dependencies |

## Process Flow (as built in Maestro)

```
Start
 └─ Get Files Detail (RPA reads 835 EDI files, converts to JSON)
     └─ Agent to Update the Data Fabric (writes ingested records to work queue)
         └─ Get Each Denial Record (loop)
             └─ Classification Agent (reads record, returns denial_type)
                 └─ Update Entity Record
                     └─ Determine Denial Type? (exclusive gateway)
                         ├─ Medical Necessity   → policy RAG → appeal letter → physician sign-off
                         ├─ Duplicate Claim      → prior-claim-paid check → close or escalate
                         ├─ Timely Filing        → deadline math → proof upload or resubmit
                         ├─ Coding Error         → Action App correction → resubmit
                         └─ Eligibility          → DOS/eligibility verification → resubmit or write-off
```

Full branch-by-branch logic (every gateway condition and node) is documented in [`maestro/process_notes.md`](./maestro/process_notes.md).

## The Five Denial Routes

| Route | CARC Codes | Handling |
|---|---|---|
| Medical Necessity | CO-50, CO-151 | RAG over payer policy → AI appeal draft → physician sign-off (SB 1120 gate) |
| Eligibility | CO-27, CO-31 | Action App verifies DOS/eligibility → resubmit or move to patient responsibility |
| Coding Error | CO-4, CO-11 | Action App for CPT/ICD correction → resubmit corrected claim |
| Duplicate | CO-18 | Prior-claim-paid check → close if true duplicate, else escalate as distinct service |
| Timely Filing | CO-29 | Deadline math against payer filing-limit table → proof upload or resubmit |

## Classification Agent

LangGraph coded agent deployed via Agent Builder, running Claude Haiku via UiPath's Bedrock wrapper.

**Pattern:** `prepare → react_agent → postprocess`

- **prepare** — reads the denial record (CARC, RARC, DOS, billed/denied/paid amounts) from the `IngestionData` Data Fabric entity
- **react_agent** — deterministic CARC→route lookup first; escalates to a Claude Haiku ReAct call only when the CARC is unmapped, or when billed/denied/paid amounts don't reconcile (partial-denial detection)
- **postprocess** — applies guardrails and returns the final classification; does **not** write to Data Fabric — persistence is handled by a downstream Maestro activity (write-decoupling for reliability)

**Guardrails:**
- Confidence < 0.70 → escalate to human (Action Center)
- `medical_necessity` → always `requires_human = true` (SB 1120, non-negotiable)
- Unmapped/conflicting CARC → defaults to `eligibility` + human flag

Full agent code is in [`agents/classification_agent/`](./agents/classification_agent/), including local-testable stubs for the Data Fabric and Bedrock calls (swapped for UiPath's native SDKs at deployment).

**Validated routing accuracy: 88/88 (100%)** against the gold-labeled test set — see [`test_data/validate_routing.py`](./test_data/validate_routing.py).

## Agent Type

**Both Coded Agents and Low-code Agents.**

- **Coded Agent (Classification Agent):** LangGraph-based, built with Claude Code (Anthropic) — external coding agent, qualifying for the judging bonus.
- **Low-code Agent (Appeal Letter Generation Agent):** Configured in Agent Builder using UiPath's low-code interface; runs the policy RAG and drafts the medical-necessity appeal letter.

## Setup Instructions

> **Note:** This is a 100% UiPath Cloud project. Maestro, Data Fabric, and Action Center/Action Apps are configured through the UiPath Cloud UI — there are no local files to clone and run for those components. This repository documents the architecture and contains the one genuinely local artifact: the classification agent's code.

### Prerequisites
- UiPath Cloud account with access to: Maestro, Agent Builder, Data Fabric, Action Center
- AWS Bedrock access configured in your UiPath tenant (for Claude Haiku)
- Python 3.10+ and `langgraph` installed locally if you want to run/test the agent outside Agent Builder

### Step 1 — Data Fabric Setup
Create an `IngestionData` entity with the following fields:

| Field | Type |
|---|---|
| `record_id` | String (primary key) |
| `claim_id` | String |
| `payer_id` | String |
| `carc_code` | String |
| `rarc_code` | String |
| `date_of_service` | Date |
| `billed_amount` | Decimal |
| `denied_amount` | Decimal |
| `paid_amount` | Decimal |
| `denial_classification` | String |
| `requires_human` | Boolean |

### Step 2 — Classification Agent Deployment
1. In Agent Builder, create a new Coded Agent
2. Upload the agent code from `/agents/classification_agent/agent.py`
3. Replace the local stub clients (`data_fabric_client.py`, `bedrock_client.py`) with calls to UiPath's native Data Fabric SDK and tenant-configured Bedrock wrapper — see `agents/classification_agent/README.md` for exact swap points
4. Set input argument: `record_id` (String)
5. Set output arguments: `record_id`, `denial_classification`, `requires_human`
6. Deploy

### Step 3 — Maestro BPMN Configuration
Build the process per the flow documented in [`maestro/process_notes.md`](./maestro/process_notes.md):
1. RPA ingestion step reads 835 EDI files and converts to JSON
2. An agent step writes ingested records into the `IngestionData` work queue
3. A loop pulls each unprocessed record and invokes the Classification Agent
4. An exclusive gateway (`Determine Denial Type?`) branches on the returned `denial_classification` into the 5 subprocesses
5. Wire each subprocess's write activity to update `IngestionData` directly in Maestro — never inside the agent

### Step 4 — Action Center / Action Apps Configuration
- **Action App — CPT Code Correction:** Coding Error branch
- **Action App — DOS/Eligibility Verification:** Eligibility branch
- **Action App — Appeal Letter Editing:** Timely Filing branch (post-deadline-validation)
- **Action Center — Physician Attestation:** Medical Necessity branch only — this is the SB 1120 compliance gate and should be the only step tracked as a formal Action Center task rather than a lightweight Action App

### Step 5 — Load Test Data
1. Place `gold_labels_88.csv` in `/test_data/` (already included in this repo)
2. Run `python test_data/validate_routing.py` to confirm 88/88 routing accuracy locally
3. The dataset includes the fully-wired hero case: `REC-0001`, David Okafor, CO-50, sepsis inpatient, Meridian MP-114 §4.2

### Running the Demo
1. Trigger ingestion with a sample 835 EDI file
2. The classification agent triages each record — check Agent Builder execution logs
3. Coding Error, Duplicate, Eligibility, and Timely Filing routes resolve through their Action Apps automatically or with light human input
4. The David Okafor medical-necessity case routes to Action Center for physician attestation
5. Approve the AI-drafted appeal in Action Center to complete the full end-to-end flow

## Repository Structure

```
ctrl-appeal/
├── README.md
├── agents/
│   └── classification_agent/
│       ├── agent.py              # LangGraph coded agent (prepare → react_agent → postprocess)
│       ├── data_fabric_client.py # Local test stub — swap for UiPath Data Fabric SDK
│       ├── bedrock_client.py     # Local test stub — swap for UiPath Bedrock wrapper
│       └── README.md
├── maestro/
│   └── process_notes.md          # Full BPMN branch-by-branch documentation
├── test_data/
│   ├── gold_labels_88.csv        # 88 gold-labeled synthetic denials
│   ├── generate_gold_labels.py   # Script used to generate the dataset
│   ├── validate_routing.py       # Validates agent accuracy against gold labels
│   ├── 835_era_sample.edi
│   └── denial_letters/
├── docs/
│   ├── architecture_diagram.png
│   └── hero_case.png
└── presentation/
    └── CtrlAppeal_AgentHack2026.pptx
```

## Key Numbers

- **$260–300B** in annual US hospital claim denials
- **65%** of denials never appealed — bandwidth constraint, not viability
- **3:1** appeal ROI on worked cases
- **45–60 min** per appeal manually → seconds with Ctrl+Appeal
- **5** denial routes handled end-to-end
- **88/88 (100%)** routing accuracy on the gold-labeled test set
- **SB 1120** compliant by construction — physician always in the loop for medical necessity
