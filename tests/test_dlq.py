from decimal import Decimal
from datetime import datetime, timezone
from backend.dedup import DeduplicationEngine
from backend.schemas import TransactionEvent
from backend.storage import Storage


def test_dlq_recording_and_redrive(tmp_path):
    storage = Storage(f"sqlite:///{tmp_path / 'dlq_test.db'}")
    engine = DeduplicationEngine(storage)

    # Insert an invalid event directly into DLQ
    with storage.transaction() as db:
        db.execute(
            "INSERT INTO dead_letter_events(event_id, payload, reason, status, created_at) VALUES (?, ?, ?, 'unresolved', ?)",
            (
                "bad-1",
                '{"event_id": "bad-1", "transaction_id": "bad-tx-1", "amount": "100.00", "sender_account": "A", "receiver_account": "B", "currency": "INR", "timestamp": "2025-01-01T00:00:00Z"}',
                "simulated network error",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    items = storage.dlq_events(page=1, page_size=10, status="unresolved")
    assert items["total"] == 1
    dlq_id = items["items"][0]["id"]

    # Redrive event
    dlq_item = storage.get_dlq_event(dlq_id)
    assert dlq_item is not None
    assert dlq_item["status"] == "unresolved"

    storage.resolve_dlq(dlq_id, status="resolved")
    resolved = storage.get_dlq_event(dlq_id)
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"] is not None
