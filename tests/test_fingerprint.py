from datetime import datetime, timezone
from decimal import Decimal
from backend.fingerprint import fingerprint_event
from backend.schemas import TransactionEvent


def test_delivery_attempt_does_not_change_fingerprint():
    values = dict(event_id="e", transaction_id="t",
                  timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                  sender_account="a", receiver_account="b",
                  amount=Decimal("10.00"))
    first = TransactionEvent(delivery_attempt=1, **values)
    replay = TransactionEvent(delivery_attempt=9, **values)
    assert fingerprint_event(first) == fingerprint_event(replay)
