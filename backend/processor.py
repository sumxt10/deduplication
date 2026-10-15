import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from .dedup import DeduplicationEngine
from .schemas import TransactionEvent


def process_csv(path, engine: DeduplicationEngine, batch_size=500, progress_callback=None):
    counters = {
        "total": 0, "accepted": 0, "duplicates": 0, "invalid": 0, "failed": 0,
        "unique_valid": 0, "ground_truth_duplicates": 0,
        "true_positive_duplicates": 0, "false_positive_duplicates": 0,
        "false_negative_duplicates": 0,
    }
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
                event_row = {key: value for key, value in row.items() if key != "ground_truth"}
                result = engine.process(TransactionEvent.model_validate(event_row))
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
                    db.execute("INSERT INTO dead_letter_events(event_id, payload, reason, created_at) VALUES (?, ?, ?, ?)",
                               (row.get("event_id"), json.dumps(row), str(exc),
                                datetime.now(timezone.utc).isoformat()))
            if progress_callback and counters["total"] % batch_size == 0:
                progress_callback(counters)
    counters["duration_ms"] = (time.perf_counter() - started) * 1000
    counters["throughput"] = counters["total"] / (counters["duration_ms"] / 1000) if counters["duration_ms"] else 0
    detected = counters["true_positive_duplicates"] + counters["false_positive_duplicates"]
    counters["duplicate_precision"] = (
        counters["true_positive_duplicates"] / detected if detected else 1.0
    )
    counters["duplicate_recall"] = (
        counters["true_positive_duplicates"] / counters["ground_truth_duplicates"]
        if counters["ground_truth_duplicates"] else 1.0
    )
    return counters