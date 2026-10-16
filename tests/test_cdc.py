from backend.cdc import CDCPipeline
from backend.dedup import DeduplicationEngine
from backend.storage import Storage


def test_cdc_simulation_generates_and_deduplicates(tmp_path):
    storage = Storage(f"sqlite:///{tmp_path / 'cdc_test.db'}")
    engine = DeduplicationEngine(storage)
    cdc = CDCPipeline(engine)

    total_events = 40
    dup_rate = 0.30
    result = cdc.simulate_cdc_stream(
        total_events=total_events,
        duplicate_rate=dup_rate,
        network_retry_burst=True,
    )

    assert result["total_streamed"] == total_events
    assert result["duplicates_injected"] > 0
    assert result["duplicates_detected"] == result["duplicates_injected"]
    assert result["duplicate_detection_accuracy"] == 100.0
    assert len(cdc.history) == total_events
    # Ensure ledger transactions only match the unique count
    assert storage.summary()["transactions"] == result["unique_original_wal"]
