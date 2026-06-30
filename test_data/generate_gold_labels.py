"""
Generates gold_labels_88.csv -- the synthetic, internally-consistent
test dataset for Ctrl+Appeal's classification agent evaluation.

88 records across 5 routes, 3 fictional payers, 1 fictional provider.
Distribution is weighted to resemble a real denial mix (medical necessity
and eligibility are the most common in practice; duplicate and timely
filing are rarer but high-value to catch).
"""

import csv
import random
from datetime import date, timedelta

random.seed(42)  # reproducible

PAYERS = [
    ("MERIDIAN", "Meridian Health (Medicare Advantage)"),
    ("ATLAS", "Atlas Commercial PPO"),
    ("BLUERIVER", "BlueRiver Medicaid MCO"),
]
PROVIDER = "Lakeview Regional"

ROUTE_CARC = {
    "medical_necessity": ["CO-50", "CO-151"],
    "eligibility":       ["CO-27", "CO-31"],
    "coding_error":      ["CO-4", "CO-11"],
    "duplicate":         ["CO-18"],
    "timely_filing":     ["CO-29"],
}

# Target distribution across 88 records (sums to 88)
ROUTE_COUNTS = {
    "medical_necessity": 24,
    "eligibility":        22,
    "coding_error":       18,
    "duplicate":          12,
    "timely_filing":      12,
}

RARC_BY_ROUTE = {
    "medical_necessity": ["N115", "M127", None],
    "eligibility":        ["N30", "N95", None],
    "coding_error":        ["M51", "M20", None],
    "duplicate":           ["N522", None],
    "timely_filing":       ["N211", None],
}

HERO_RECORD = {
    "record_id": "REC-0001",
    "claim_id": "CLM-OKAFOR-9001",
    "payer_id": "MERIDIAN",
    "carc_code": "CO-50",
    "rarc_code": "N115",
    "date_of_service": "2026-03-14",
    "billed_amount": 48250.00,
    "denied_amount": 48250.00,
    "paid_amount": 0.00,
    "denial_classification": "medical_necessity",
    "requires_human": True,
    "notes": "David Okafor -- sepsis inpatient -- hero case, policy MP-114 sec 4.2",
}


def random_date(start_year=2025, end_year=2026):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    delta_days = (end - start).days
    return start + timedelta(days=random.randint(0, delta_days))


def generate_amounts(route: str):
    """
    Generate billed/denied/paid amounts that reconcile (billed = denied + paid),
    except for an intentional ~15% partial-denial subset to exercise the
    agent's amount-reconciliation / confidence-lowering logic.
    """
    billed = round(random.uniform(150, 52000), 2)
    is_partial = random.random() < 0.15

    if is_partial:
        paid = round(billed * random.uniform(0.1, 0.6), 2)
        denied = round(billed - paid, 2)
    else:
        paid = 0.00
        denied = billed

    return billed, denied, paid


def generate_record(idx: int, route: str):
    payer_id, _ = random.choice(PAYERS)
    carc = random.choice(ROUTE_CARC[route])
    rarc = random.choice(RARC_BY_ROUTE[route])
    dos = random_date()
    billed, denied, paid = generate_amounts(route)

    requires_human = route == "medical_necessity"  # SB 1120 guardrail

    return {
        "record_id": f"REC-{idx:04d}",
        "claim_id": f"CLM-{random.randint(10000,99999)}",
        "payer_id": payer_id,
        "carc_code": carc,
        "rarc_code": rarc if rarc else "",
        "date_of_service": dos.isoformat(),
        "billed_amount": billed,
        "denied_amount": denied,
        "paid_amount": paid,
        "denial_classification": route,
        "requires_human": requires_human,
        "notes": "",
    }


def main():
    records = [HERO_RECORD]
    idx = 2

    for route, count in ROUTE_COUNTS.items():
        # subtract 1 from medical_necessity count since hero record covers one slot
        n = count - 1 if route == "medical_necessity" else count
        for _ in range(n):
            records.append(generate_record(idx, route))
            idx += 1

    random.shuffle(records[1:])  # keep hero record first, shuffle the rest

    assert len(records) == 88, f"Expected 88 records, got {len(records)}"

    fieldnames = [
        "record_id", "claim_id", "payer_id", "carc_code", "rarc_code",
        "date_of_service", "billed_amount", "denied_amount", "paid_amount",
        "denial_classification", "requires_human", "notes",
    ]

    with open("gold_labels_88.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Wrote {len(records)} records to gold_labels_88.csv")

    # Quick distribution summary
    from collections import Counter
    dist = Counter(r["denial_classification"] for r in records)
    for route, count in dist.items():
        print(f"  {route}: {count}")


if __name__ == "__main__":
    main()
