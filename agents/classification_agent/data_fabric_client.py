"""
Thin wrapper around UiPath Data Fabric's record-retrieval API.

In production (deployed via Agent Builder), this resolves to UiPath's
native Data Fabric SDK call. This stub exists so the agent code is
readable and testable outside the UiPath runtime -- e.g. with
Claude Code during development.
"""

import csv
import os

_DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "test_data", "gold_labels_88.csv")


def get_entity_record_by_id(entity_name: str, record_id: str) -> dict:
    """
    Mock implementation: reads from the local gold_labels_88.csv test
    dataset instead of a live Data Fabric entity. Swap this for the real
    UiPath Data Fabric SDK call when running inside Agent Builder:

        from uipath.data_fabric import DataFabricClient
        client = DataFabricClient()
        return client.get_record(entity_name, record_id)
    """
    if entity_name != "IngestionData":
        raise ValueError(f"Unknown entity: {entity_name}")

    if not os.path.exists(_DATA_FILE):
        raise FileNotFoundError(
            f"Test data file not found at {_DATA_FILE}. "
            f"Place gold_labels_88.csv in /test_data/ for local testing."
        )

    with open(_DATA_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["record_id"] == record_id:
                return {
                    "carc_code": row["carc_code"],
                    "rarc_code": row.get("rarc_code") or None,
                    "date_of_service": row.get("date_of_service"),
                    "billed_amount": float(row["billed_amount"]) if row.get("billed_amount") else None,
                    "denied_amount": float(row["denied_amount"]) if row.get("denied_amount") else None,
                    "paid_amount": float(row["paid_amount"]) if row.get("paid_amount") else None,
                    "payer_id": row.get("payer_id"),
                    "claim_id": row.get("claim_id"),
                }

    raise KeyError(f"record_id {record_id} not found in test dataset")
