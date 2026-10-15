from dataclasses import dataclass
from datetime import datetime, timezone
from .bloom_filter import SlidingWindowBloomFilter
from .fingerprint import fingerprint_event
from .schemas import TransactionEvent
from .storage import Storage


@dataclass
class ProcessResult:
    status: str
    event_id: str
    transaction_id: str
    reason: str | None = None


class DeduplicationEngine:
    def __init__(self, storage: Storage, bloom=None):
        self.storage = storage
        self.bloom = bloom or SlidingWindowBloomFilter()

    def process(self, event: TransactionEvent) -> ProcessResult:
        fingerprint = fingerprint_event(event)
        now = datetime.now(timezone.utc).isoformat()
        payload = event.model_dump_json()
        possible = fingerprint in self.bloom
        with self.storage.transaction() as db:
            existing = db.execute("SELECT * FROM processed_events WHERE event_id = ?",
                                  (event.event_id,)).fetchone()
            if existing:
                status = "duplicate" if existing["fingerprint"] == fingerprint else "conflict"
                reason = "repeated delivery" if status == "duplicate" else "event_id payload conflict"
                db.execute("INSERT INTO processed_events(event_id, transaction_id, fingerprint, payload, status, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (event.event_id, event.transaction_id, fingerprint, payload, status, reason, now))
                self.bloom.add(fingerprint)
                if status == "duplicate":
                    self.bloom.confirmed_duplicates += 1
                return ProcessResult(status, event.event_id, event.transaction_id, reason)
            existing_tx = db.execute("SELECT * FROM transactions WHERE transaction_id = ?",
                                     (event.transaction_id,)).fetchone()
            if existing_tx:
                same_payload = (
                    existing_tx["sender_account"] == event.sender_account
                    and existing_tx["receiver_account"] == event.receiver_account
                    and existing_tx["amount_paise"] == int(event.amount * 100)
                    and existing_tx["currency"] == event.currency
                    and existing_tx["created_at"] == event.timestamp.isoformat()
                )
                status = "duplicate" if same_payload else "conflict"
                reason = ("transaction_id already committed under another event"
                          if same_payload else "transaction_id payload conflict")
                db.execute("INSERT INTO processed_events(event_id, transaction_id, fingerprint, payload, status, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (event.event_id, event.transaction_id, fingerprint, payload, status, reason, now))
                self.bloom.add(fingerprint)
                if status == "duplicate":
                    self.bloom.confirmed_duplicates += 1
                return ProcessResult(status, event.event_id, event.transaction_id, reason)
            amount_paise = int(event.amount * 100)
            for account in (event.sender_account, event.receiver_account):
                db.execute("INSERT OR IGNORE INTO accounts(account_id, balance_paise) VALUES (?, 0)",
                           (account,))
            db.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (event.transaction_id, event.event_id, event.sender_account,
                        event.receiver_account, amount_paise, event.currency, event.timestamp.isoformat()))
            db.execute("UPDATE accounts SET balance_paise = balance_paise - ? WHERE account_id = ?",
                       (amount_paise, event.sender_account))
            db.execute("UPDATE accounts SET balance_paise = balance_paise + ? WHERE account_id = ?",
                       (amount_paise, event.receiver_account))
            for account, direction in ((event.sender_account, "debit"), (event.receiver_account, "credit")):
                db.execute("INSERT INTO ledger_entries(transaction_id, account, direction, amount_paise, created_at) VALUES (?, ?, ?, ?, ?)",
                           (event.transaction_id, account, direction, amount_paise, now))
            db.execute("INSERT INTO processed_events(event_id, transaction_id, fingerprint, payload, status, reason, created_at) VALUES (?, ?, ?, ?, 'accepted', NULL, ?)",
                       (event.event_id, event.transaction_id, fingerprint, payload, now))
            self.bloom.add(fingerprint)
            if possible:
                self.bloom.false_positives += 1
            return ProcessResult("accepted", event.event_id, event.transaction_id)