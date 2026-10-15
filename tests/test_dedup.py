from datetime import datetime, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from backend.dedup import DeduplicationEngine
from backend.schemas import TransactionEvent
from backend.storage import Storage


def event(event_id="e1", transaction_id="t1"):
    return TransactionEvent(event_id=event_id, transaction_id=transaction_id,
                            timestamp=datetime.now(timezone.utc), sender_account="a",
                            receiver_account="b", amount=Decimal("10.00"))


def test_replay_has_no_second_financial_effect(tmp_path):
    engine = DeduplicationEngine(Storage(f"sqlite:///{tmp_path / 'test.db'}"))
    original = event()
    assert engine.process(original).status == "accepted"
    assert engine.process(original).status == "duplicate"
    assert engine.storage.summary()["transactions"] == 1
    assert engine.storage.summary()["accepted"] == 1


def test_concurrent_replays_commit_once(tmp_path):
    engine = DeduplicationEngine(Storage(f"sqlite:///{tmp_path / 'concurrent.db'}"))
    original = event()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: engine.process(original).status, range(8)))
    assert results.count("accepted") == 1
    assert results.count("duplicate") == 7
    assert engine.storage.summary()["transactions"] == 1