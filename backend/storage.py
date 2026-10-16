"""Unified persistent storage layer supporting both SQLite and PostgreSQL.

Enforces:
1. Atomic ACID transactions for double-entry financial accounting.
2. Dialect translation between SQLite and PostgreSQL (e.g., autoincrement, upsert, placeholders).
3. Thread-safe connection pooling and immediate lock acquisition for idempotency.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from pathlib import Path
import sqlite3
import threading
from typing import Any

logger = logging.getLogger("ps15.storage")


class DualRow(dict):
    """Dictionary row that also supports integer indexing like sqlite3.Row."""

    def __init__(self, cols: list[str], vals: tuple | list):
        super().__init__(zip(cols, vals))
        self._vals = tuple(vals)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._vals[key]
        return super().__getitem__(key)


class DBAdapter:
    """Standardized database execution adapter providing uniform ? placeholder syntax."""

    def __init__(self, conn, dialect: str = "sqlite"):
        self.conn = conn
        self.dialect = dialect

    def execute(self, sql: str, params: tuple | list = ()):
        if self.dialect == "postgres":
            # Translate SQLite idioms to PostgreSQL
            # Replace '?' with '%s'
            translated_sql = sql.replace("?", "%s")
            # Replace 'INSERT OR IGNORE' with 'ON CONFLICT DO NOTHING'
            if "INSERT OR IGNORE INTO accounts" in translated_sql:
                translated_sql = translated_sql.replace(
                    "INSERT OR IGNORE INTO accounts(account_id, balance_paise) VALUES (%s, 0)",
                    "INSERT INTO accounts(account_id, balance_paise) VALUES (%s, 0) ON CONFLICT (account_id) DO NOTHING"
                )
            cur = self.conn.cursor()
            cur.execute(translated_sql, params or ())
            return PostgresCursorWrapper(cur)
        else:
            return self.conn.execute(sql, params or ())

    def executescript(self, script: str):
        if self.dialect == "postgres":
            cur = self.conn.cursor()
            cur.execute(script)
            return cur
        else:
            return self.conn.executescript(script)


class PostgresCursorWrapper:
    """Wraps a psycopg cursor to return DualRow instances compatible with sqlite3.Row."""

    def __init__(self, cursor):
        self.cursor = cursor

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        if self.cursor.description:
            cols = [desc.name for desc in self.cursor.description]
            return DualRow(cols, row)
        return row

    def fetchall(self):
        rows = self.cursor.fetchall()
        if not rows or not self.cursor.description:
            return []
        cols = [desc.name for desc in self.cursor.description]
        return [DualRow(cols, r) for r in rows]

    @property
    def rowcount(self):
        return self.cursor.rowcount


class Storage:
    def __init__(self, database_url: str = "sqlite:///./data/ps15.db"):
        self.database_url = database_url
        self.is_postgres = database_url.startswith("postgresql://") or database_url.startswith("postgres://")
        self.dialect = "postgres" if self.is_postgres else "sqlite"
        self._lock = threading.RLock()

        if self.is_postgres:
            try:
                import psycopg
                self._psycopg = psycopg
            except ImportError:
                raise RuntimeError(
                    "PostgreSQL was specified in DATABASE_URL, but 'psycopg' is not installed. "
                    "Install with: pip install 'psycopg[binary]>=3.1'"
                )
        else:
            path = database_url.removeprefix("sqlite:///")
            self.path = Path(path)
            if not self.path.is_absolute():
                self.path = Path.cwd() / self.path
            self.path.parent.mkdir(parents=True, exist_ok=True)

        self.initialize()

    def connection(self):
        if self.is_postgres:
            conn = self._psycopg.connect(self.database_url, autocommit=False)
            return conn
        else:
            connection = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            return connection

    @contextmanager
    def transaction(self):
        with self._lock:
            conn = self.connection()
            adapter = DBAdapter(conn, dialect=self.dialect)
            try:
                if self.is_postgres:
                    # PostgreSQL transaction starts automatically; execute queries inside block
                    yield adapter
                    conn.commit()
                else:
                    conn.execute("BEGIN IMMEDIATE")
                    yield adapter
                    conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def initialize(self):
        if self.is_postgres:
            ddl = """
            CREATE TABLE IF NOT EXISTS processed_events (
                id BIGSERIAL PRIMARY KEY,
                event_id TEXT NOT NULL,
                transaction_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_processed_event ON processed_events(event_id);
            CREATE INDEX IF NOT EXISTS ix_processed_tx ON processed_events(transaction_id);
            CREATE INDEX IF NOT EXISTS ix_processed_fp ON processed_events(fingerprint);

            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                sender_account TEXT NOT NULL,
                receiver_account TEXT NOT NULL,
                amount_paise BIGINT NOT NULL,
                currency TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ledger_entries (
                id BIGSERIAL PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                account TEXT NOT NULL,
                direction TEXT NOT NULL,
                amount_paise BIGINT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                balance_paise BIGINT NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS dead_letter_events (
                id BIGSERIAL PRIMARY KEY,
                event_id TEXT,
                payload TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'unresolved',
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_dlq_status ON dead_letter_events(status);

            CREATE TABLE IF NOT EXISTS demo_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                config TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                total INTEGER NOT NULL,
                accepted INTEGER NOT NULL DEFAULT 0,
                duplicates INTEGER NOT NULL DEFAULT 0,
                invalid INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                duration_ms DOUBLE PRECISION,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
            with self.transaction() as db:
                db.executescript(ddl)
        else:
            ddl = """
            CREATE TABLE IF NOT EXISTS processed_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL, transaction_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL, payload TEXT NOT NULL,
                status TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_processed_event ON processed_events(event_id);
            CREATE INDEX IF NOT EXISTS ix_processed_tx ON processed_events(transaction_id);
            CREATE INDEX IF NOT EXISTS ix_processed_fp ON processed_events(fingerprint);

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
                reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'unresolved',
                created_at TEXT NOT NULL, resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS demo_jobs (
                job_id TEXT PRIMARY KEY, status TEXT NOT NULL, config TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL,
                accepted INTEGER NOT NULL DEFAULT 0, duplicates INTEGER NOT NULL DEFAULT 0,
                invalid INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0,
                duration_ms REAL, result TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            """
            with self.transaction() as db:
                db.executescript(ddl)
                try:
                    db.execute("ALTER TABLE dead_letter_events ADD COLUMN status TEXT NOT NULL DEFAULT 'unresolved'")
                except sqlite3.OperationalError:
                    pass
                try:
                    db.execute("ALTER TABLE dead_letter_events ADD COLUMN resolved_at TEXT")
                except sqlite3.OperationalError:
                    pass
                try:
                    db.execute("CREATE INDEX IF NOT EXISTS ix_dlq_status ON dead_letter_events(status)")
                except sqlite3.OperationalError:
                    pass

    def reset(self):
        with self.transaction() as db:
            for table in ("ledger_entries", "transactions", "processed_events",
                          "dead_letter_events", "accounts", "demo_jobs"):
                db.execute(f"DELETE FROM {table}")

    def summary(self):
        with self.transaction() as db:
            counts = {
                row["status"]: row["count"]
                for row in db.execute(
                    "SELECT status, COUNT(*) AS count FROM processed_events GROUP BY status"
                ).fetchall()
            }
            invalid_row = db.execute("SELECT COUNT(*) FROM dead_letter_events").fetchone()
            invalid = invalid_row[0] if invalid_row else 0

            unresolved_row = db.execute(
                "SELECT COUNT(*) FROM dead_letter_events WHERE status = 'unresolved'"
            ).fetchone()
            unresolved_dlq = unresolved_row[0] if unresolved_row else 0

            tx_row = db.execute("SELECT COUNT(*) FROM transactions").fetchone()
            acc_row = db.execute("SELECT COUNT(*) FROM accounts").fetchone()

            return {
                "total_deliveries": sum(counts.values()) + invalid,
                "accepted": counts.get("accepted", 0),
                "duplicates": counts.get("duplicate", 0),
                "conflicts": counts.get("conflict", 0),
                "invalid": invalid,
                "unresolved_dlq": unresolved_dlq,
                "transactions": tx_row[0] if tx_row else 0,
                "accounts": acc_row[0] if acc_row else 0,
            }

    def events(self, page=1, page_size=50, status=None):
        with self.transaction() as db:
            where, values = (" WHERE status = ?", [status]) if status else ("", [])
            total_row = db.execute("SELECT COUNT(*) FROM processed_events" + where, values).fetchone()
            total = total_row[0] if total_row else 0

            rows = db.execute(
                "SELECT * FROM processed_events" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
                values + [page_size, (page - 1) * page_size],
            ).fetchall()
            return {
                "items": [dict(row) for row in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    def dlq_events(self, page=1, page_size=50, status=None):
        with self.transaction() as db:
            where, values = (" WHERE status = ?", [status]) if status else ("", [])
            total_row = db.execute("SELECT COUNT(*) FROM dead_letter_events" + where, values).fetchone()
            total = total_row[0] if total_row else 0

            rows = db.execute(
                "SELECT * FROM dead_letter_events" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
                values + [page_size, (page - 1) * page_size],
            ).fetchall()
            return {
                "items": [dict(row) for row in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    def get_dlq_event(self, dlq_id: int):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM dead_letter_events WHERE id = ?", (dlq_id,)).fetchone()
            return dict(row) if row else None

    def resolve_dlq(self, dlq_id: int, status: str = "resolved"):
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as db:
            db.execute(
                "UPDATE dead_letter_events SET status = ?, resolved_at = ? WHERE id = ?",
                (status, now, dlq_id),
            )

    def delete_dlq(self, dlq_id: int):
        with self.transaction() as db:
            db.execute("DELETE FROM dead_letter_events WHERE id = ?", (dlq_id,))