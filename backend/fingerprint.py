"""Canonical SHA-256 identity for an event's stable payload."""
import hashlib
import json
from decimal import Decimal
from .schemas import TransactionEvent


def canonical_event(event: TransactionEvent) -> str:
    values = {
        "event_id": event.event_id, "transaction_id": event.transaction_id,
        "timestamp": event.timestamp.isoformat(timespec="microseconds"),
        "sender_account": event.sender_account, "receiver_account": event.receiver_account,
        "amount": format(Decimal(event.amount), "f"), "currency": event.currency.upper(),
        "transaction_type": event.transaction_type, "schema_version": event.schema_version,
        "source": event.source,
    }
    return json.dumps(values, sort_keys=True, separators=(",", ":"))


def fingerprint_event(event: TransactionEvent) -> str:
    return hashlib.sha256(canonical_event(event).encode("utf-8")).hexdigest()