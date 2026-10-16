from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import random

from backend.dedup import DeduplicationEngine
from backend.schemas import TransactionEvent
from backend.storage import Storage


def create_sample_event(i: int):
    return TransactionEvent(
        event_id=f"chaos-test-evt-{i:05d}",
        transaction_id=f"chaos-test-tx-{i:05d}",
        sender_account=f"ACC-{random.randint(1000, 9999)}",
        receiver_account=f"ACC-{random.randint(10000, 99999)}",
        amount=Decimal("150.00"),
        currency="INR",
        timestamp=datetime.now(timezone.utc),
        transaction_type="transfer",
        schema_version=1,
        source="unit_test",
    )


def test_high_concurrency_duplicate_flood(tmp_path):
    storage = Storage(f"sqlite:///{tmp_path / 'chaos_test.db'}")
    engine = DeduplicationEngine(storage)

    total_unique = 100
    duplicate_count = 50

    unique_events = [create_sample_event(i) for i in range(total_unique)]
    duplicates = [random.choice(unique_events) for _ in range(duplicate_count)]
    all_deliveries = unique_events + duplicates
    random.shuffle(all_deliveries)

    with ThreadPoolExecutor(max_workers=16) as pool:
        statuses = list(pool.map(lambda ev: engine.process(ev).status, all_deliveries))

    accepted = statuses.count("accepted")
    dups = statuses.count("duplicate")

    # Invariants
    assert accepted == total_unique, f"Expected {total_unique} accepted, got {accepted}"
    assert dups == duplicate_count, f"Expected {duplicate_count} duplicates, got {dups}"

    summary = storage.summary()
    assert summary["accepted"] == total_unique
    assert summary["duplicates"] == duplicate_count
    assert summary["transactions"] == total_unique

    # Verify ledger consistency:
    # Each accepted transfer creates 2 ledger entries (debit + credit)
    with storage.connection() as db:
        ledger_count = db.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()[0]
        assert ledger_count == total_unique * 2

        # Net balance of ledger must balance to 0 (double-entry invariant)
        debit_sum = db.execute("SELECT SUM(amount_paise) FROM ledger_entries WHERE direction = 'debit'").fetchone()[0] or 0
        credit_sum = db.execute("SELECT SUM(amount_paise) FROM ledger_entries WHERE direction = 'credit'").fetchone()[0] or 0
        assert debit_sum == credit_sum, f"Ledger imbalance: {debit_sum} != {credit_sum}"
