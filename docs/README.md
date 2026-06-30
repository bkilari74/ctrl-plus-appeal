# Classification Agent

LangGraph coded agent for denial classification, deployed via UiPath Agent Builder.

## Files

| File | Purpose |
|---|---|
| `agent.py` | Main agent: `prepare → react_agent → postprocess` graph |
| `data_fabric_client.py` | Data Fabric read wrapper (mocked locally against `/test_data/gold_labels_88.csv`; swap for UiPath's native SDK in deployment) |
| `bedrock_client.py` | Claude Haiku invocation wrapper (mocked locally with a safe low-confidence fallback; swap for UiPath's Bedrock wrapper in deployment) |

## Local testing

```bash
cd agents/classification_agent
python agent.py REC-0001
```

## Validating against the full gold-label set

```bash
cd test_data
python validate_routing.py
```

This reports routing accuracy against all 88 gold-labeled records in `gold_labels_88.csv`.

## Deployment notes

When deploying to Agent Builder:
1. Replace `data_fabric_client.get_entity_record_by_id` with a call to UiPath's native Data Fabric SDK
2. Replace `bedrock_client.invoke_claude_haiku` with UiPath's tenant-configured Bedrock wrapper call
3. The `run(record_id)` function is the entry point Agent Builder should invoke
4. Confirm the downstream Maestro activity (not this agent) handles the Data Fabric write of `denial_classification` and `requires_human` back to the `IngestionData` entity
