from backend.dedup import DeduplicationEngine
from backend.processor import process_csv
from backend.storage import Storage
from scripts.generate_transactions import generate


def test_processor_reports_ground_truth_accuracy(tmp_path):
    csv_path = tmp_path / "workload.csv"
    generate(csv_path, total=20, duplicate_rate=0.30, invalid_rate=0.10, seed=9)
    result = process_csv(csv_path, DeduplicationEngine(Storage(f"sqlite:///{tmp_path / 'db.sqlite'}")))
    assert result["total"] == 20
    assert result["unique_valid"] == 12
    assert result["ground_truth_duplicates"] == 6
    assert result["true_positive_duplicates"] == 6
    assert result["duplicate_precision"] == 1.0
    assert result["duplicate_recall"] == 1.0
