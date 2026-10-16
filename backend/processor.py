import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from .dedup import DeduplicationEngine
from .metrics import percentile
from .schemas import TransactionEvent


def normalize_event_row(row: dict) -> dict:
    """Normalizes both synthetic and PaySim dataset rows into a valid TransactionEvent dictionary."""
    clean = {k: v for k, v in row.items() if k != "ground_truth"}
    if "sender_account" not in clean and "nameOrig" in clean:
        clean["sender_account"] = clean["nameOrig"]
    if "receiver_account" not in clean and "nameDest" in clean:
        clean["receiver_account"] = clean["nameDest"]
    if "currency" not in clean:
        clean["currency"] = "INR"
    if "transaction_type" not in clean:
        clean["transaction_type"] = "transfer"
    if "schema_version" not in clean:
        clean["schema_version"] = 1
    if "source" not in clean:
        clean["source"] = "dataset"
    return clean


def process_csv(path, engine: DeduplicationEngine, batch_size=500, progress_callback=None):
    counters = {
        "total": 0, "accepted": 0, "duplicates": 0, "invalid": 0, "failed": 0,
        "unique_valid": 0, "ground_truth_duplicates": 0,
        "true_positive_duplicates": 0, "false_positive_duplicates": 0,
        "false_negative_duplicates": 0,
    }
    latencies_us = []
    started = time.perf_counter()

    with Path(path).open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            counters["total"] += 1
            ground_truth = row.get("ground_truth", "")
            if ground_truth == "duplicate":
                counters["ground_truth_duplicates"] += 1
            elif ground_truth == "unique":
                counters["unique_valid"] += 1

            try:
                event_data = normalize_event_row(row)
                result = engine.process(TransactionEvent.model_validate(event_data))
                latencies_us.append(result.latency_us)

                if result.status == "accepted":
                    counters["accepted"] += 1
                elif result.status == "duplicate":
                    counters["duplicates"] += 1
                    if ground_truth == "duplicate":
                        counters["true_positive_duplicates"] += 1
                    elif ground_truth == "unique":
                        counters["false_positive_duplicates"] += 1
                else:
                    counters["failed"] += 1

                if ground_truth == "duplicate" and result.status != "duplicate":
                    counters["false_negative_duplicates"] += 1

            except Exception as exc:
                counters["invalid"] += 1
                with engine.storage.transaction() as db:
                    db.execute(
                        "INSERT INTO dead_letter_events(event_id, payload, reason, status, created_at) VALUES (?, ?, ?, 'unresolved', ?)",
                        (row.get("event_id"), json.dumps(row), str(exc),
                         datetime.now(timezone.utc).isoformat()),
                    )

            if progress_callback and counters["total"] % batch_size == 0:
                progress_callback(counters)

    duration_s = time.perf_counter() - started
    counters["duration_ms"] = round(duration_s * 1000, 2)
    counters["throughput"] = round(counters["total"] / duration_s, 2) if duration_s > 0 else 0.0

    detected = counters["true_positive_duplicates"] + counters["false_positive_duplicates"]
    counters["duplicate_precision"] = (
        round(counters["true_positive_duplicates"] / detected, 4) if detected else 1.0
    )
    counters["duplicate_recall"] = (
        round(counters["true_positive_duplicates"] / counters["ground_truth_duplicates"], 4)
        if counters["ground_truth_duplicates"] else 1.0
    )

    # Latency percentiles (converted to ms)
    if latencies_us:
        p50 = percentile(latencies_us, 0.50) / 1000.0
        p95 = percentile(latencies_us, 0.95) / 1000.0
        p99 = percentile(latencies_us, 0.99) / 1000.0
        avg = (sum(latencies_us) / len(latencies_us)) / 1000.0
    else:
        p50 = p95 = p99 = avg = 0.0

    counters["latency"] = {
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "p99_ms": round(p99, 3),
        "avg_ms": round(avg, 3),
    }
    counters["bloom_memory_bytes"] = engine.bloom.memory_bytes if hasattr(engine.bloom, "memory_bytes") else 0
    counters["bloom_false_positives"] = getattr(engine.bloom, "false_positives", 0)

    return counters