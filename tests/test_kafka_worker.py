from datetime import datetime, timezone
from decimal import Decimal
import json

from backend.dedup import DeduplicationEngine
from backend.kafka_worker import KafkaWorker
from backend.schemas import TransactionEvent
from backend.storage import Storage


class MockKafkaMessage:
    def __init__(self, value: bytes | str, error_val=None):
        self._val = value if isinstance(value, (bytes, bytearray)) else value.encode("utf-8")
        self._error = error_val

    def value(self):
        return self._val

    def error(self):
        return self._error


class MockKafkaConsumer:
    def __init__(self, messages):
        self.messages = list(messages)
        self.committed = []
        self.closed = False

    def poll(self, timeout=1.0):
        if self.messages:
            return self.messages.pop(0)
        return None

    def commit(self, message=None, asynchronous=False):
        self.committed.append(message)

    def close(self):
        self.closed = True


def test_kafka_worker_valid_and_duplicate_events(tmp_path):
    storage = Storage(f"sqlite:///{tmp_path / 'kafka_test.db'}")
    engine = DeduplicationEngine(storage)

    event_payload = {
        "event_id": "k-evt-001",
        "transaction_id": "k-tx-001",
        "sender_account": "ACC-KAFKA-1",
        "receiver_account": "ACC-KAFKA-2",
        "amount": "1250.00",
        "currency": "INR",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transaction_type": "transfer",
        "schema_version": 1,
        "source": "kafka_stream",
    }
    raw_json = json.dumps(event_payload)

    # 1 original message followed by 1 duplicate replay
    mock_messages = [
        MockKafkaMessage(raw_json),
        MockKafkaMessage(raw_json),
    ]
    mock_consumer = MockKafkaConsumer(mock_messages)

    worker = KafkaWorker(engine=engine, consumer=mock_consumer)
    worker.run(max_messages=2)

    # Verify both messages had their offsets committed
    assert len(mock_consumer.committed) == 2
    assert mock_consumer.closed is True

    # Invariants in persistent storage:
    # Exactly one financial effect committed
    summary = storage.summary()
    assert summary["accepted"] == 1
    assert summary["duplicates"] == 1
    assert summary["transactions"] == 1

    # Ledger must have 2 entries (1 debit, 1 credit) for the single committed tx
    with storage.connection() as db:
        ledger = db.execute("SELECT * FROM ledger_entries").fetchall()
        assert len(ledger) == 2


def test_kafka_worker_poison_pill_quarantined_to_dlq(tmp_path):
    storage = Storage(f"sqlite:///{tmp_path / 'kafka_dlq.db'}")
    engine = DeduplicationEngine(storage)

    # Poison pills: 1 invalid JSON string, 1 schema violation (missing sender_account & negative amount)
    mock_messages = [
        MockKafkaMessage("THIS IS NOT JSON {{{{{"),
        MockKafkaMessage(json.dumps({"event_id": "bad-schema-1", "amount": -50.0})),
    ]
    mock_consumer = MockKafkaConsumer(mock_messages)

    worker = KafkaWorker(engine=engine, consumer=mock_consumer)
    # The worker must NOT crash on poison pills
    worker.run(max_messages=2)

    # Both offsets must be committed so Kafka does not crash loop
    assert len(mock_consumer.committed) == 2

    # Both poisoned messages must be safely quarantined in DLQ
    dlq = storage.dlq_events()
    assert dlq["total"] == 2
    assert dlq["items"][0]["status"] == "unresolved"


def test_kafka_worker_crash_and_redelivery_safety(tmp_path):
    storage = Storage(f"sqlite:///{tmp_path / 'kafka_crash.db'}")
    engine = DeduplicationEngine(storage)

    event_payload = {
        "event_id": "crash-evt-001",
        "transaction_id": "crash-tx-001",
        "sender_account": "ACC-CRASH-1",
        "receiver_account": "ACC-CRASH-2",
        "amount": "800.00",
        "currency": "INR",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transaction_type": "transfer",
        "schema_version": 1,
        "source": "kafka_stream",
    }
    raw_json = json.dumps(event_payload)

    # Worker 1 processes the event, but "crashes" before committing offset
    worker1 = KafkaWorker(engine=engine)
    res1 = worker1.process_single_message(MockKafkaMessage(raw_json))
    assert res1["status"] == "accepted"

    # Worker 2 restarts and re-polls the same uncommitted message
    worker2 = KafkaWorker(engine=engine)
    res2 = worker2.process_single_message(MockKafkaMessage(raw_json))
    # Engine must detect duplicate and prevent second financial effect
    assert res2["status"] == "duplicate"

    summary = storage.summary()
    assert summary["accepted"] == 1
    assert summary["duplicates"] == 1
    assert summary["transactions"] == 1
