# Ctrl+Appeal — Intelligent Denial Management & Appeals Automation

## Project Description

Ctrl+Appeal is a provider-side, agentic denial management and appeals automation system built entirely on UiPath Cloud. It ingests healthcare claim denials from any source (835 ERA files, payer portal RPA, faxed letters via Document Understanding), classifies each into one of five denial routes using a LangGraph classification agent, handles each route end-to-end, and keeps a licensed physician in the loop for every medical-necessity determination — satisfying California SB 1120 by construction.

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
| **Maestro BPMN** | 5-branch exclusive gateway, 7-phase process orchestration, long-running 30/60/90-day timer events for response tracking |
| **Agent Builder** | Hosts three agents: Ingestion Agent, Classification Agent (LangGraph/coded), Appeal Drafter Agent |
| **Data Fabric** | IngestionData entity for denial records, classification result persistence, payer policy document store |
| **Action Center** | Billing specialist review queue; physician attestation tasks for SB 1120 compliance gate |
| **Studio Web** | All process logic, Data Fabric R/W, route branch activities — zero desktop dependencies |
| **Document Understanding** | OCR and extraction for faxed/scanned denial letters |

## The Five Denial Routes

| Route | CARC Codes | Handling |
|---|---|---|
| Medical Necessity | CO-50, CO-151 | RAG over payer policy → AI appeal draft → physician sign-off (SB 1120 gate) |
| Eligibility | CO-27, CO-31 | Re-verify eligibility at date of service → resubmit or move to patient responsibility |
| Coding Error | CO-4, CO-11 | Coder corrects CPT/ICD codes → resubmit corrected claim |
| Duplicate | CO-18 | ICN-first composite-key claims history match → close if true duplicate, else appeal as distinct |
| Timely Filing | CO-29 | Deadline math against payer filing-limit table → file exception with proof, or write-off |

## Agent Type

**Both Coded Agents and Low-code Agents.**

- **Coded Agent (Classification Agent):** LangGraph-based, deployed via Agent Builder. Uses the UiPath starter template adapted to run Claude Haiku via UiPath's Bedrock wrapper. Pattern: `prepare → react_agent → postprocess`. Built with Claude Code (Anthropic) — external coding agent, qualifying for the judging bonus.
- **Low-code Agents (Ingestion Agent, Appeal Drafter Agent):** Configured in Agent Builder using UiPath's low-code interface.

## Setup Instructions

> **Note:** This is a 100% UiPath Cloud project. All components are configured through the UiPath Cloud UI — there are no local files to clone and run. The repository contains documentation, exported agent definitions, test data, and architecture artifacts.

### Prerequisites
- UiPath Cloud account with access to: Maestro, Agent Builder, Data Fabric, Action Center, Studio Web
- AWS Bedrock access configured in your UiPath tenant (for Claude Haiku)
- UiPath Document Understanding license

### Step 1 — Data Fabric Setup
In Data Fabric, create an entity named `IngestionData` with the following fields:

| Field | Type |
|---|---|
| `record_id` | String (primary key) |
| `carc_code` | String |
| `rarc_code` | String |
| `date_of_service` | Date |
| `billed_amount` | Decimal |
| `denied_amount` | Decimal |
| `paid_amount` | Decimal |
| `denial_classification` | String |
| `requires_human` | Boolean |
| `payer_id` | String |
| `claim_id` | String |

### Step 2 — Classification Agent Deployment
1. In Agent Builder, create a new Coded Agent
2. Upload the LangGraph agent code from `/agents/classification_agent/`
3. Configure the Bedrock connection to Claude Haiku
4. Set input arguments: `record_id` (String)
5. Set output arguments: `record_id` (String), `denial_classification` (String), `requires_human` (Boolean)
6. Deploy the agent

**Guardrails built into the agent:**
- Confidence < 0.70 → routes to human review (Action Center)
- `medical_necessity` → always `requires_human = true` (SB 1120 compliance)
- Unknown/conflicting CARC → defaults to `eligibility` + human flag
- Write is decoupled: agent reads and classifies only; a downstream Maestro activity handles all Data Fabric writes

### Step 3 — Maestro BPMN Configuration
In Maestro, configure the main process with the following exclusive gateway branches:

| Branch condition | Subprocess |
|---|---|
| `denial_classification == "medical_necessity"` | Medical Necessity subprocess (RAG + appeal draft + Action Center) |
| `denial_classification == "eligibility"` | Eligibility subprocess |
| `denial_classification == "coding_error"` | Coding Error subprocess |
| `denial_classification == "duplicate"` | Duplicate Claim subprocess |
| `denial_classification == "timely_filing"` | Timely Filing subprocess |

Wire the Classification Agent invocation so the result is persisted by a dedicated Maestro Data Fabric write activity — not by the agent itself.

### Step 4 — Action Center Configuration
Create two task types in Action Center:
- **Specialist Review:** Assigned to billing team queue
- **Physician Attestation:** Assigned to physician queue — this is the SB 1120 gate, triggered only on the `medical_necessity` route

### Step 5 — Load Test Data
1. Load the synthetic dataset from `/test_data/` into Data Fabric
2. The depth set (10 claims) covers all 5 routes, including the fully-wired hero case: David Okafor, CO-50, sepsis inpatient, Meridian MP-114 §4.2
3. Gold-label classification file at `/test_data/gold_labels_88.csv` for measuring routing accuracy

### Running the Demo
1. Trigger ingestion by uploading the sample 835 ERA file from `/test_data/835_era_sample.edi`
2. The classification agent triages all claims — check Agent Builder execution logs
3. Technical denials (Duplicate, Timely Filing, Coding Error, Eligibility) process through their respective Maestro subprocesses automatically
4. The David Okafor CO-50 case routes to Action Center for physician attestation
5. Approve the AI-drafted appeal in Action Center to complete the full end-to-end flow

## Repository Structure

```
ctrl-appeal/
├── README.md
├── agents/
│   └── classification_agent/     # LangGraph coded agent (Claude Haiku via Bedrock)
├── maestro/
│   └── process_notes.md          # BPMN branch logic and phase documentation
├── test_data/
│   ├── 835_era_sample.edi
│   ├── gold_labels_88.csv
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
- **7** process phases
- **88** gold-labeled denials in evaluation dataset
- **SB 1120** compliant by construction — physician always in the loop
