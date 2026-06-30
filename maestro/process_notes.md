# Maestro BPMN — Process Notes

This document describes the actual Maestro BPMN process built for Ctrl+Appeal, covering ingestion, classification routing, and all five denial-route subprocesses.

## High-Level Flow

```
Start Event
   └─► Get Files Detail (RPA: reads 835 EDI files from storage, converts to JSON)
        └─► Agent to Update the Data Fabric (writes ingested records as a work queue)
             └─► Get Each Denial Record (loop)
                  ├─► [No Claim Available] → End
                  └─► [New Record Available]
                       └─► Classification Agent (reads JSON, assigns denial_type)
                            └─► Update Entity Record
                                 └─► Determine Denial Type? (exclusive gateway)
                                      ├─► Medical Necessity
                                      ├─► Duplicate Claim
                                      ├─► Timely Filing
                                      ├─► Coding Error
                                      └─► Eligibility
```

The Classification Agent is invoked once per denial record pulled from the Data Fabric work queue. Its only job is to read the record and return a `denial_type` — all branch handling happens downstream in Maestro, not inside the agent.

## Branch 1 — Medical Necessity

```
Determine if Medical Necessity Is Valid (exclusive gateway)
   └─► Claim-Denial-is-Valid
        └─► Send email that denial is valid
   └─► Generate Appeal for Denial
        └─► Agent for appeal letter generation
             └─► Medical Necessity – Appeal Letter (entity update)
                  └─► Appeal Denied? (exclusive gateway)
                       ├─► Appeal-Letter = Approved
                       │    └─► Update Entity Record
                       │         └─► Send Email For Medical Necessity (approved)
                       └─► Appeal-Letter = Denied
                            └─► Send Email – Appeal Denied
                                 └─► Update Entity Record
```

This is the only branch with a human-in-the-loop gate (physician attestation via Action Center, per SB 1120) before the appeal letter is finalized and sent.

## Branch 2 — Duplicate Claim

```
Search for Duplicate Claim
   └─► Prior Claim Was Paid? (exclusive gateway)
        ├─► Prior-Claim-Was-Paid
        │    └─► Send Email – Resubmit Original Claim
        └─► Prior-Claim-Was-Not-Paid
             └─► [continues to Timely Filing check — claim treated as distinct service]
```

A true duplicate (prior claim already paid) is closed with a resubmit-original-claim notice. A false positive (prior claim not paid) is routed onward as a distinct service requiring its own filing-deadline check.

## Branch 3 — Timely Filing

```
Calculate Filing Deadline
   └─► Filing-Deadline-is-Valid? (exclusive gateway)
        ├─► Filing-Deadline-is-Valid
        │    └─► Send Email – Filing Deadline Is Valid
        │         └─► Action App for Appeal Letter Editing
        │              └─► Update Entity Record
        │                   └─► Send Email – Appeal Denied [terminal, if appeal ultimately rejected]
        └─► Filing-Deadline-is-Invalid
             └─► App to Upload Proof of Timely Filing
                  └─► Appeal Letter Generation
                       └─► Update Entity Record
                            └─► Send Email For Timely Filing Denial
                                 └─► Appeal-Letter = Approved? (exclusive gateway)
                                      ├─► Approved → Update Entity Record
                                      └─► Denied   → Send Email – Appeal Denied
```

Deadline math runs against the payer filing-limit table. If the deadline was met, the system proceeds straight to appeal letter editing. If missed, the user is prompted to upload proof of timely submission before an appeal letter is generated.

## Branch 4 — Coding Error

```
Action App to Correct CPT Codes
   └─► Send Email – CPT Code Updated
        └─► Update Entity Record
```

This is the simplest branch — a human corrects the CPT/ICD code via an Action App, the system records the update, and notifies the work queue owner.

## Branch 5 — Eligibility

```
Create Action App to Verify DOS (Date of Service) and Eligibility
   └─► Date-of-Service-Updated? (exclusive gateway)
        ├─► Date-of-Service-Updated
        │    └─► [routes back into Timely Filing Denial flow — DOS change requires re-filing check]
        └─► No-Change-in-DOS
             └─► Send Email – Eligibility Denial Is Valid
```

If the date of service is corrected, supporting documentation must be attached and the claim is sent back through the timely-filing check (since a DOS change can affect the filing deadline). If DOS is confirmed unchanged, the denial is valid and the claim moves to patient responsibility.

## Notes on Design

- **Agent boundary:** Every "Agent" node in the BPMN (Classification Agent, Appeal Letter Generation Agent, Data Fabric Update Agent) performs reasoning/extraction only. All entity writes happen in dedicated Maestro activities downstream of the agent call — this is the write-decoupling pattern used throughout the process for reliability.
- **Action Apps vs. Action Center:** Lower-stakes human touchpoints (CPT correction, DOS verification, appeal letter editing) use lightweight Action Apps embedded in the flow. The single SB 1120-relevant touchpoint — physician attestation on Medical Necessity appeals — is the only step that should route through Action Center as a tracked compliance task.
- **Email nodes:** Used as both notifications (work queue owner is informed of a change) and decision-record touchpoints in the BPMN diagram, distinguishing system actions (auto-resolved) from items still pending the user's review.
- **Two intersecting timer/deadline paths:** Both the Timely Filing branch and the Eligibility branch ultimately depend on a valid Date of Service and a valid Filing Deadline — the BPMN reuses the Timely Filing Denial path when Eligibility resolution changes the DOS.
