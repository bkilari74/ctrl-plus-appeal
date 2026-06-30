"""
Validates the classification agent's routing accuracy against the
88-record gold-labeled test set.
"""
import csv
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents", "classification_agent"))
from agent import run

CSV_PATH = os.path.join(os.path.dirname(__file__), "gold_labels_88.csv")


def main():
    total = 0
    correct = 0
    mismatches = []

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            record_id = row["record_id"]
            expected = row["denial_classification"]

            result = run(record_id)
            actual = result["denial_classification"]

            if actual == expected:
                correct += 1
            else:
                mismatches.append((record_id, expected, actual))

    accuracy = correct / total * 100
    print(f"Routing accuracy: {correct}/{total} ({accuracy:.1f}%)")

    if mismatches:
        print(f"\n{len(mismatches)} mismatches:")
        for record_id, expected, actual in mismatches[:10]:
            print(f"  {record_id}: expected={expected} actual={actual}")
        if len(mismatches) > 10:
            print(f"  ... and {len(mismatches) - 10} more")


if __name__ == "__main__":
    main()
