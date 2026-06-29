# Ctrl+Appeal — Intelligent Denial Management & Appeals Automation

## Project Description

Ctrl+Appeal is a provider-side, agentic denial management and appeals automation system built entirely on UiPath Cloud. It ingests healthcare claim denials from any source (835 ERA files, payer portal RPA, faxed letters via Document Understanding), classifies each into one of five denial routes using a LangGraph classification agent, handles each route end-to-end, and keeps a licensed physician in the loop for every medical-necessity determination — satisfying California SB 1120 by construction.

**The problem it solves:** US hospitals receive $260–300B in claim denials annually. ~65% are never appealed — not because appeals fail (3:1 ROI), but because the manual process (2–4 hrs/appeal) exhausts bandwidth before timely-filing deadlines pass. Ctrl+Appeal eliminates that bottleneck while preserving physician authority over clinical decisions.

## UiPath Components

| Component | Usage |
|---|---|
| **Maestro BPMN** | 5-branch exclusive gateway, 7-phase process orchestration, long-running 30/60/90-day timer events for response tracking |
| **Agent Builder** | Hosts three agents: Ingestion Agent, Classification Agent (LangGraph/coded), Appeal Drafter Agent |
| **Data Fabric** | IngestionData entity for denial records, classification result persistence, payer policy document store |
| **Action Center** | Billing specialist review queue; physician attestation tasks for SB 1120 compliance gate |
| **Studio Web** | All process logic, Data Fabric R/W, route branch activities — zero desktop dependencies |
| **UiPath Apps** | Billing specialist UI: denial + AI-drafted appeal letter side-by-side with approve/edit/escalate controls |
| **Document Understanding** | OCR and extraction for faxed/scanned denial letters |

## Agent Type

**Both Coded Agents and Low-code Agents.**

- **Coded Agent (Classification Agent):** LangGraph-based, deployed via Agent Builder. Uses the UiPath starter template adapted to run Claude Haiku via UiPath's Bedrock wrapper. Pattern: `prepare → react_agent → postprocess`. Built with Claude Code (Anthropic) — external coding agent, qualifying for the judging bonus.
- **Low-code Agents (Ingestion Agent, Appeal Drafter Agent):** Configured in Agent Builder using UiPath's low-code interface.

## Setup Instructions

### Prerequisites
- UiPath Cloud account with access to: Maestro, Agent Builder, Data Fabric, Action Center, Studio Web, UiPath Apps
- AWS Bedrock access (for Claude Haiku via UiPath's Bedrock wrapper)
- UiPath Document Understanding license

### Step 1 — Data Fabric Setup
1. In Data Fabric, create an entity named `IngestionData` with the following fields:
   - `record_id` (String, primary key)
   - `carc_code` (String)
   - `rarc_code` (String)
   - `date_of_service` (Date)
   - `billed_amount` (Decimal)
   - `denied_amount` (Decimal)
   - `paid_amount` (Decimal)
   - `denial_classification` (String)
   - `requires_human` (Boolean)
   - `payer_id` (String)
   - `claim_id` (String)

### Step 2 — Classification Agent Deployment
1. In Agent Builder, create a new Coded Agent
2. Upload the LangGraph classification agent code from `/agents/classification_agent/`
3. Configure the Bedrock connection to Claude Haiku
4. Set input arguments: `record_id` (String)
5. Set output arguments: `record_id` (String), `denial_classification` (String), `requires_human` (Boolean)
6. Deploy the agent

### Step 3 — Maestro BPMN Import
1. In Maestro, import the process definition from `/maestro/ctrl_appeal_main.bpmn`
2. Configure the exclusive gateway branch conditions:
   - `medical_necessity` → Medical Necessity subprocess
   - `eligibility` → Eligibility subprocess
   - `coding_error` → Coding Error subprocess
   - `duplicate` → Duplicate Claim subprocess
   - `timely_filing` → Timely Filing subprocess
3. Wire the Classification Agent call to the Data Fabric write step (decoupled — agent reads, Maestro writes)

### Step 4 — Action Center Configuration
1. Create two task types in Action Center:
   - **Specialist Review:** Assigned to billing team queue
   - **Physician Attestation:** Assigned to physician queue (SB 1120 gate — medical_necessity route only)
2. Configure escalation rules: unworked tasks > 48hrs escalate to supervisor

### Step 5 — UiPath Apps
1. Import the app definition from `/apps/specialist_review_app/`
2. Connect to the `IngestionData` Data Fabric entity and Action Center task queue
3. Publish and assign access to billing specialist role

### Step 6 — Load Test Data
1. Load the synthetic dataset from `/test_data/` into Data Fabric
2. The depth set (10 claims) covers all 5 routes including the hero case (David Okafor, CO-50, sepsis)
3. Gold-label classification file at `/test_data/gold_labels_88.csv` for routing accuracy validation

### Running the Demo
1. Trigger ingestion by uploading the sample 835 ERA file from `/test_data/835_era_sample.edi`
2. The classification agent will triage all claims — check Agent Builder execution logs
3. Technical denials (Duplicate, Timely Filing) will process automatically
4. The David Okafor CO-50 case will route to Action Center for physician review
5. Approve the AI-drafted appeal in Action Center to complete the end-to-end flow
