from backend.dedup import DeduplicationEngine
from backend.processor import process_csv
from backend.storage import Storage
from scripts.generate_paysim import generate_paysim_workload


def test_paysim_generation_and_processing(tmp_path):
    csv_path = tmp_path / "paysim_sample.csv"
    info = generate_paysim_workload(
        output_path=str(csv_path),
        total=200,
        duplicate_rate=0.30,
        invalid_rate=0.01,
        seed=123,
    )

    assert info["total"] == 200
    assert info["duplicates"] == 60
    assert info["unique_valid"] == 138

    storage = Storage(f"sqlite:///{tmp_path / 'paysim_test.db'}")
    engine = DeduplicationEngine(storage)
    counters = process_csv(csv_path, engine, batch_size=50)

    assert counters["total"] == 200
    assert counters["accepted"] == 138
    assert counters["duplicates"] == 60
    assert counters["invalid"] == 2
    assert counters["duplicate_recall"] == 1.0
    assert counters["duplicate_precision"] == 1.0
    assert "latency" in counters
    assert counters["latency"]["p50_ms"] >= 0.0
    assert counters["latency"]["p99_ms"] >= 0.0
