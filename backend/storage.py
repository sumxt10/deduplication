from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading


class Storage:
    def __init__(self, database_url="sqlite:///./data/ps15.db"):
        path = database_url.removeprefix("sqlite:///")
        self.path = Path(path)
        if not self.path.is_absolute():
            self.path = Path.cwd() / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.initialize()

    def connection(self):
        connection = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def transaction(self):
        with self._lock:
            connection = self.connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def initialize(self):
        with self.transaction() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS processed_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL, transaction_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL, payload TEXT NOT NULL,
                status TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_processed_event ON processed_events(event_id);
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
                sender_account TEXT NOT NULL, receiver_account TEXT NOT NULL,
                amount_paise INTEGER NOT NULL, currency TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ledger_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT, transaction_id TEXT NOT NULL,
                account TEXT NOT NULL, direction TEXT NOT NULL, amount_paise INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY, balance_paise INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS dead_letter_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT, payload TEXT NOT NULL,
                reason TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS demo_jobs (
                job_id TEXT PRIMARY KEY, status TEXT NOT NULL, config TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL,
                accepted INTEGER NOT NULL DEFAULT 0, duplicates INTEGER NOT NULL DEFAULT 0,
                invalid INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0,
                duration_ms REAL, result TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            """)

    def reset(self):
        with self.transaction() as db:
            for table in ("ledger_entries", "transactions", "processed_events",
                          "dead_letter_events", "accounts", "demo_jobs"):
                db.execute(f"DELETE FROM {table}")

    def summary(self):
        db = self.connection()
        try:
            counts = {row["status"]: row["count"] for row in db.execute(
                "SELECT status, COUNT(*) count FROM processed_events GROUP BY status")}
            invalid = db.execute("SELECT COUNT(*) FROM dead_letter_events").fetchone()[0]
            return {"total_deliveries": sum(counts.values()) + invalid, "accepted": counts.get("accepted", 0),
                    "duplicates": counts.get("duplicate", 0), "conflicts": counts.get("conflict", 0),
                    "invalid": invalid,
                    "transactions": db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]}
        finally:
            db.close()

    def events(self, page=1, page_size=50, status=None):
        db = self.connection()
        try:
            where, values = (" WHERE status = ?", [status]) if status else ("", [])
            total = db.execute("SELECT COUNT(*) FROM processed_events" + where, values).fetchone()[0]
            rows = db.execute("SELECT * FROM processed_events" + where +
                              " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                              values + [page_size, (page - 1) * page_size]).fetchall()
            return {"items": [dict(row) for row in rows], "total": total,
                    "page": page, "page_size": page_size}
        finally:
            db.close()