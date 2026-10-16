"""Change Data Capture (CDC) pipeline and WAL (Write-Ahead Log) streaming emulator.

Simulates enterprise CDC mechanisms (e.g., Debezium tailing PostgreSQL WAL / MySQL binlog):
1. Reads source database state mutations with Log Sequence Numbers (LSN) and transaction IDs.
2. Packages mutations into standard Debezium-compatible CDC event envelopes.
3. Injects realistic network delivery anomalies (retry bursts, rebalance re-reads, duplicate deliveries ~30%).
4. Streams events into Kafka or directly into the DeduplicationEngine.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import random
import time
from typing import Any
from .dedup import DeduplicationEngine
from .schemas import TransactionEvent


@dataclass
class CDCMetadata:
    connector: str
    db: str
    table: str
    tx_id: int
    lsn: int
    ts_ms: int
    op: str  # "c" for create/insert, "u" for update, "d" for delete


@dataclass
class CDCRecord:
    source: CDCMetadata
    op: str
    ts_ms: int
    before: dict[str, Any] | None
    after: dict[str, Any]
    delivery_attempt: int = 1
    is_simulated_retry: bool = False

    def to_event(self) -> TransactionEvent:
        """Converts the CDC after-state payload into a canonical TransactionEvent."""
        payload = dict(self.after)
        payload["delivery_attempt"] = self.delivery_attempt
        payload["source"] = f"cdc_{self.source.connector}"
        return TransactionEvent.model_validate(payload)


class CDCPipeline:
    def __init__(self, engine: DeduplicationEngine | None = None):
        self.engine = engine
        self._current_lsn = 100_000_000
        self._current_tx_id = 50_000
        self.history: list[dict] = []
        self.stats = {
            "wal_records_generated": 0,
            "events_streamed": 0,
            "duplicates_injected": 0,
            "retries_simulated": 0,
        }

    def generate_wal_change(
        self,
        sender: str,
        receiver: str,
        amount: str,
        event_id: str | None = None,
        tx_id: str | None = None,
    ) -> CDCRecord:
        """Simulates an INSERT into the core banking transactions table captured from WAL."""
        self._current_lsn += random.randint(128, 4096)
        self._current_tx_id += 1
        now = datetime.now(timezone.utc)
        ts_ms = int(now.timestamp() * 1000)

        eid = event_id or f"evt-cdc-{self._current_tx_id:08d}"
        tid = tx_id or f"tx-cdc-{self._current_tx_id:08d}"

        metadata = CDCMetadata(
            connector="postgres_wal",
            db="core_banking",
            table="transactions",
            tx_id=self._current_tx_id,
            lsn=self._current_lsn,
            ts_ms=ts_ms,
            op="c",
        )

        after_state = {
            "event_id": eid,
            "transaction_id": tid,
            "timestamp": now.isoformat(),
            "sender_account": sender,
            "receiver_account": receiver,
            "amount": amount,
            "currency": "INR",
            "transaction_type": "transfer",
            "schema_version": 1,
        }

        self.stats["wal_records_generated"] += 1
        return CDCRecord(
            source=metadata,
            op="c",
            ts_ms=ts_ms,
            before=None,
            after=after_state,
            delivery_attempt=1,
            is_simulated_retry=False,
        )

    def simulate_cdc_stream(
        self,
        total_events: int = 50,
        duplicate_rate: float = 0.30,
        network_retry_burst: bool = True,
        delay_ms: int = 0,
    ) -> dict:
        """Executes a simulated CDC streaming run with realistic retry bursts and duplicates."""
        if not self.engine:
            raise RuntimeError("DeduplicationEngine required for CDC stream execution")

        results = []
        records_to_stream: list[CDCRecord] = []
        unique_count = max(1, int(total_events * (1.0 - duplicate_rate)))
        dup_count = total_events - unique_count

        # Step 1: Generate original WAL events
        originals: list[CDCRecord] = []
        for i in range(unique_count):
            sender = f"ACC-CDC-{random.randint(100, 999):05d}"
            receiver = f"ACC-CDC-{random.randint(1000, 1999):05d}"
            amount = f"{round(random.uniform(100.0, 25000.0), 2):.2f}"
            record = self.generate_wal_change(sender, receiver, amount)
            originals.append(record)
            records_to_stream.append(record)

        # Step 2: Inject duplicate deliveries (simulating at-least-once message broker retries)
        for i in range(dup_count):
            base_rec = originals[i % len(originals)]
            # Duplicate retains identical transaction state, with delivery_attempt incremented
            dup_rec = CDCRecord(
                source=base_rec.source,
                op="c",
                ts_ms=base_rec.ts_ms,
                before=None,
                after=dict(base_rec.after),
                delivery_attempt=base_rec.delivery_attempt + 1,
                is_simulated_retry=True,
            )
            self.stats["duplicates_injected"] += 1
            if network_retry_burst:
                self.stats["retries_simulated"] += 1
            records_to_stream.append(dup_rec)

        # Shuffle if burst simulation is enabled
        if not network_retry_burst:
            random.shuffle(records_to_stream)

        # Step 3: Stream through Deduplication Engine
        accepted = 0
        duplicates = 0
        conflicts = 0

        for rec in records_to_stream:
            event = rec.to_event()
            res = self.engine.process(event)
            self.stats["events_streamed"] += 1

            if res.status == "accepted":
                accepted += 1
            elif res.status == "duplicate":
                duplicates += 1
            elif res.status == "conflict":
                conflicts += 1

            results.append({
                "lsn": rec.source.lsn,
                "tx_id": rec.source.tx_id,
                "event_id": event.event_id,
                "transaction_id": event.transaction_id,
                "is_retry": rec.is_simulated_retry,
                "delivery_attempt": rec.delivery_attempt,
                "status": res.status,
                "reason": res.reason,
                "latency_us": res.latency_us,
            })

            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

        # Store latest 200 stream results for UI inspection
        self.history = (results + self.history)[:200]

        return {
            "total_streamed": len(records_to_stream),
            "unique_original_wal": unique_count,
            "duplicates_injected": dup_count,
            "accepted": accepted,
            "duplicates_detected": duplicates,
            "conflicts": conflicts,
            "duplicate_detection_accuracy": (
                round((duplicates / dup_count) * 100, 2) if dup_count > 0 else 100.0
            ),
            "latest_lsn": self._current_lsn,
            "results": results,
        }
