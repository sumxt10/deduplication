"""PaySim mobile money dataset transformer and synthetic workload generator.

Supports:
1. Generating deterministic streaming PaySim-style financial transaction workloads
   with realistic account patterns, fraud flags, and configurable duplicate injection (~30%).
2. Transforming existing Kaggle PaySim CSV files (PS_201743927192_1491204439457_log.csv)
   into canonical TransactionEvent streams with injected duplicate deliveries.
"""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random

PAYSIM_FIELDS = [
    "step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig",
    "nameDest", "oldbalanceDest", "newbalanceDest", "isFraud", "isFlaggedFraud",
    "event_id", "transaction_id", "timestamp", "sender_account", "receiver_account",
    "currency", "transaction_type", "schema_version", "source", "ground_truth"
]


def generate_paysim_workload(
    output_path: str,
    total: int = 1000,
    duplicate_rate: float = 0.30,
    invalid_rate: float = 0.01,
    fraud_rate: float = 0.02,
    seed: int = 42,
) -> dict:
    if duplicate_rate + invalid_rate >= 1.0:
        raise ValueError("duplicate_rate + invalid_rate must be less than 1.0")

    duplicates = int(total * duplicate_rate)
    invalid = int(total * invalid_rate)
    unique = total - duplicates - invalid
    if unique < 1:
        raise ValueError("total records too small to accommodate unique records")

    rng = random.Random(seed)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    base_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    originals = []

    # Pool of accounts to simulate realistic multi-transfer banking behavior
    senders = [f"C{rng.randrange(100000000, 999999999)}" for _ in range(max(10, unique // 5))]
    receivers = [f"M{rng.randrange(100000000, 999999999)}" for _ in range(max(10, unique // 5))]

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAYSIM_FIELDS)
        writer.writeheader()

        # Step 1: Generate unique valid PaySim transactions
        for i in range(unique):
            step = (i // 100) + 1  # 1 hour per 100 txns
            tx_type = rng.choice(["TRANSFER", "PAYMENT", "CASH_OUT"])
            amount_val = round(rng.uniform(10.0, 50000.0), 2)
            name_orig = rng.choice(senders)
            name_dest = rng.choice(receivers)
            while name_dest == name_orig:
                name_dest = f"M{rng.randrange(100000000, 999999999)}"

            old_orig = round(rng.uniform(amount_val, amount_val * 3), 2)
            new_orig = round(old_orig - amount_val, 2)
            old_dest = round(rng.uniform(0.0, 20000.0), 2)
            new_dest = round(old_dest + amount_val, 2)

            is_fraud = 1 if (rng.random() < fraud_rate and tx_type == "TRANSFER") else 0
            is_flagged = 1 if (is_fraud and amount_val > 200000) else 0

            ts = (base_time + timedelta(seconds=i * 5)).isoformat()
            event_id = f"evt-paysim-{seed}-{i:07d}"
            tx_id = f"tx-paysim-{seed}-{i:07d}"

            record = {
                "step": step,
                "type": tx_type,
                "amount": f"{amount_val:.2f}",
                "nameOrig": name_orig,
                "oldbalanceOrg": f"{old_orig:.2f}",
                "newbalanceOrig": f"{new_orig:.2f}",
                "nameDest": name_dest,
                "oldbalanceDest": f"{old_dest:.2f}",
                "newbalanceDest": f"{new_dest:.2f}",
                "isFraud": is_fraud,
                "isFlaggedFraud": is_flagged,
                "event_id": event_id,
                "transaction_id": tx_id,
                "timestamp": ts,
                "sender_account": name_orig,
                "receiver_account": name_dest,
                "currency": "INR",
                "transaction_type": "transfer",
                "schema_version": 1,
                "source": "paysim",
                "ground_truth": "unique",
            }
            originals.append(record)
            writer.writerow(record)

        # Step 2: Inject duplicate deliveries (~30%)
        # Duplicates retain the exact same event_id, transaction_id, accounts, amount, and timestamp
        for i in range(duplicates):
            source_rec = originals[i % unique]
            dup_record = dict(source_rec)
            dup_record["ground_truth"] = "duplicate"
            writer.writerow(dup_record)

        # Step 3: Inject malformed / invalid events (~1%) to verify Dead Letter Queue isolation
        for i in range(invalid):
            source_rec = originals[(i + duplicates) % unique]
            invalid_record = dict(source_rec)
            invalid_record["event_id"] = f"invalid-paysim-{seed}-{i:05d}"
            invalid_record["amount"] = "-500.00"  # Negative amount violates schema
            invalid_record["ground_truth"] = "invalid"
            writer.writerow(invalid_record)

    return {
        "dataset": "PaySim",
        "output": str(output),
        "total": total,
        "unique_valid": unique,
        "duplicates": duplicates,
        "invalid": invalid,
        "duplicate_rate": duplicate_rate,
        "seed": seed,
    }


def transform_raw_kaggle_paysim(
    raw_csv_path: str,
    output_path: str,
    max_records: int = 5000,
    duplicate_rate: float = 0.30,
    seed: int = 42,
) -> dict:
    """Transforms a raw downloaded Kaggle PaySim log file into our pipeline format."""
    raw_path = Path(raw_csv_path)
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw Kaggle file not found at: {raw_csv_path}")

    rng = random.Random(seed)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    base_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    extracted = []

    with raw_path.open("r", newline="", encoding="utf-8") as src:
        reader = csv.DictReader(src)
        for i, row in enumerate(reader):
            if i >= max_records:
                break
            # Filter for transfers or payment types
            if row.get("type") not in ("TRANSFER", "PAYMENT", "CASH_OUT"):
                continue

            step = int(row.get("step", 1))
            amount_val = float(row.get("amount", 100.0))
            name_orig = row.get("nameOrig", f"C{i:08d}")
            name_dest = row.get("nameDest", f"M{i:08d}")
            if name_orig == name_dest:
                name_dest = f"{name_dest}_dest"

            ts = (base_time + timedelta(hours=step, seconds=i % 3600)).isoformat()
            rec = {
                "step": step,
                "type": row.get("type", "TRANSFER"),
                "amount": f"{amount_val:.2f}",
                "nameOrig": name_orig,
                "oldbalanceOrg": row.get("oldbalanceOrg", "0.00"),
                "newbalanceOrig": row.get("newbalanceOrig", "0.00"),
                "nameDest": name_dest,
                "oldbalanceDest": row.get("oldbalanceDest", "0.00"),
                "newbalanceDest": row.get("newbalanceDest", "0.00"),
                "isFraud": row.get("isFraud", "0"),
                "isFlaggedFraud": row.get("isFlaggedFraud", "0"),
                "event_id": f"evt-kaggle-{i:07d}",
                "transaction_id": f"tx-kaggle-{i:07d}",
                "timestamp": ts,
                "sender_account": name_orig,
                "receiver_account": name_dest,
                "currency": "INR",
                "transaction_type": "transfer",
                "schema_version": 1,
                "source": "kaggle_paysim",
                "ground_truth": "unique",
            }
            extracted.append(rec)

    total_extracted = len(extracted)
    duplicates_count = int(total_extracted * duplicate_rate)

    with output.open("w", newline="", encoding="utf-8") as dst:
        writer = csv.DictWriter(dst, fieldnames=PAYSIM_FIELDS)
        writer.writeheader()
        for rec in extracted:
            writer.writerow(rec)
        for i in range(duplicates_count):
            dup = dict(extracted[i % total_extracted])
            dup["ground_truth"] = "duplicate"
            writer.writerow(dup)

    return {
        "dataset": "Kaggle-PaySim-Transformed",
        "output": str(output),
        "total_emitted": total_extracted + duplicates_count,
        "unique_valid": total_extracted,
        "duplicates": duplicates_count,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PaySim dataset generator and transformer")
    parser.add_argument("--output", default="data/paysim_workload.csv")
    parser.add_argument("--total", type=int, default=1000)
    parser.add_argument("--duplicate-rate", type=float, default=0.30)
    parser.add_argument("--invalid-rate", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--raw-kaggle-file", default=None)
    args = parser.parse_args()

    if args.raw_kaggle_file:
        res = transform_raw_kaggle_paysim(args.raw_kaggle_file, args.output, args.total, args.duplicate_rate, args.seed)
    else:
        res = generate_paysim_workload(args.output, args.total, args.duplicate_rate, args.invalid_rate, seed=args.seed)
    print(res)
