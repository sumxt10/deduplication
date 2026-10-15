"""Deterministic, streaming synthetic workload generator."""
import argparse
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


FIELDS = ["event_id", "transaction_id", "timestamp", "sender_account",
          "receiver_account", "amount", "currency", "transaction_type",
          "schema_version", "source", "ground_truth"]


def generate(output, total=1000, duplicate_rate=0.30, invalid_rate=0.01, seed=42):
    if duplicate_rate + invalid_rate >= 1:
        raise ValueError("rates must sum to less than 1")
    duplicates = int(total * duplicate_rate)
    invalid = int(total * invalid_rate)
    unique = total - duplicates - invalid
    if unique < 1:
        raise ValueError("configuration must leave at least one unique valid event")
    rng = random.Random(seed)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    originals = []
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for index in range(unique):
            event = {"event_id": f"evt-{seed}-{index:08d}", "transaction_id": f"txn-{seed}-{index:08d}",
                     "timestamp": (datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=index)).isoformat(),
                     "sender_account": f"ACC-{rng.randrange(1, 10000):05d}",
                     "receiver_account": f"ACC-{rng.randrange(10001, 20000):05d}",
                     "amount": f"{rng.randint(100, 100000) / 100:.2f}", "currency": "INR",
                     "transaction_type": "transfer", "schema_version": "1", "source": "synthetic",
                     "ground_truth": "unique"}
            originals.append(event)
            writer.writerow(event)
        for index in range(duplicates):
            event = dict(originals[index % unique])
            event["ground_truth"] = "duplicate"
            writer.writerow(event)
        for index in range(invalid):
            event = dict(originals[(index + duplicates) % unique])
            event.update(event_id=f"invalid-{seed}-{index}", amount="-1", ground_truth="invalid")
            writer.writerow(event)
    return {"total": total, "unique_valid": unique, "duplicates": duplicates, "invalid": invalid,
            "seed": seed, "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/transactions.csv")
    parser.add_argument("--total", type=int, default=1000)
    parser.add_argument("--duplicate-rate", type=float, default=0.30)
    parser.add_argument("--invalid-rate", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(generate(args.output, args.total, args.duplicate_rate, args.invalid_rate, args.seed))