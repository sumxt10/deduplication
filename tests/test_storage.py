from datetime import datetime, timezone
from backend.storage import DBAdapter, DualRow, Storage


def test_storage_initializes(tmp_path):
    storage = Storage(f"sqlite:///{tmp_path / 'test.db'}")
    summary = storage.summary()
    assert summary["total_deliveries"] == 0
    assert summary["accepted"] == 0
    assert summary["transactions"] == 0
    assert summary["accounts"] == 0


def test_dual_row_indexing_and_key_access():
    row = DualRow(["event_id", "status", "count"], ["evt-001", "accepted", 42])
    # Key access
    assert row["event_id"] == "evt-001"
    assert row["status"] == "accepted"
    assert row["count"] == 42
    # Index access
    assert row[0] == "evt-001"
    assert row[1] == "accepted"
    assert row[2] == 42


def test_storage_events_and_dlq_crud(tmp_path):
    storage = Storage(f"sqlite:///{tmp_path / 'test_crud.db'}")
    now = datetime.now(timezone.utc).isoformat()

    # 1. Insert processed event
    with storage.transaction() as db:
        db.execute(
            "INSERT INTO processed_events(event_id, transaction_id, fingerprint, payload, status, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("e-100", "t-100", "fp-100", "{}", "accepted", None, now),
        )
        db.execute(
            "INSERT INTO dead_letter_events(event_id, payload, reason, status, created_at) "
            "VALUES (?, ?, ?, 'unresolved', ?)",
            ("e-bad", "{bad}", "syntax error", now),
        )

    # 2. Check summary and pagination
    summary = storage.summary()
    assert summary["accepted"] == 1
    assert summary["invalid"] == 1
    assert summary["unresolved_dlq"] == 1

    events = storage.events(page=1, page_size=10)
    assert events["total"] == 1
    assert events["items"][0]["event_id"] == "e-100"

    dlq = storage.dlq_events(page=1, page_size=10, status="unresolved")
    assert dlq["total"] == 1
    dlq_id = dlq["items"][0]["id"]

    # 3. Resolve and delete DLQ
    storage.resolve_dlq(dlq_id, status="resolved")
    assert storage.summary()["unresolved_dlq"] == 0

    storage.delete_dlq(dlq_id)
    assert storage.dlq_events()["total"] == 0


class DummyConn:
    def __init__(self):
        self.executed_sql = []
        self.executed_params = []

    def cursor(self):
        class DummyCur:
            def __init__(outer_self):
                pass
            def execute(inner_self, sql, params):
                self.executed_sql.append(sql)
                self.executed_params.append(params)
        return DummyCur()


def test_db_adapter_dialect_translation():
    dummy = DummyConn()
    adapter = DBAdapter(dummy, dialect="postgres")

    # Verify placeholder translation
    adapter.execute("SELECT * FROM processed_events WHERE event_id = ? AND status = ?", ("e-1", "accepted"))
    assert adapter.conn.executed_sql[0] == "SELECT * FROM processed_events WHERE event_id = %s AND status = %s"
    assert adapter.conn.executed_params[0] == ("e-1", "accepted")

    # Verify upsert translation
    adapter.execute("INSERT OR IGNORE INTO accounts(account_id, balance_paise) VALUES (?, 0)", ("acc-1",))
    assert "ON CONFLICT (account_id) DO NOTHING" in adapter.conn.executed_sql[1]
