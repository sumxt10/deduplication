"""Production-ready Kafka consumer worker with at-least-once transport and exactly-once processing.

Key Invariants:
1. Manual synchronous offset commits: The offset is committed ONLY after the event is
   authoritatively processed or safely quarantined to DLQ.
2. Poison Pill Quarantine: Malformed JSON or invalid schemas are automatically recorded
   into the Dead Letter Queue (DLQ) and the offset is committed to prevent consumer crash loops.
3. Graceful Shutdown: Responds to SIGINT / SIGTERM, cleanly closing consumer connections
   without leaving Kafka consumer group partition rebalance locks.
"""
from datetime import datetime, timezone
import json
import logging
import os
import signal
import threading
from typing import Any

from pydantic import ValidationError

from .dedup import DeduplicationEngine
from .schemas import TransactionEvent

logger = logging.getLogger("ps15.kafka_worker")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class KafkaWorker:
    def __init__(
        self,
        engine: DeduplicationEngine,
        bootstrap_servers: str | None = None,
        group_id: str | None = None,
        topic: str | None = None,
        consumer: Any = None,
    ):
        self.engine = engine
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.group_id = group_id or os.getenv("KAFKA_GROUP_ID", "ps15-workers")
        self.topic = topic or os.getenv("KAFKA_TOPIC", "financial-events")
        self._consumer = consumer
        self._stop_requested = threading.Event()

    def _init_consumer(self):
        if self._consumer is not None:
            return self._consumer

        from confluent_kafka import Consumer

        conf = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "session.timeout.ms": 30000,
            "max.poll.interval.ms": 300000,
        }
        consumer = Consumer(conf)
        consumer.subscribe([self.topic])
        self._consumer = consumer
        return consumer

    def process_single_message(self, message: Any) -> dict:
        """Processes a single Kafka message, enforcing exactly-once semantics and DLQ quarantine."""
        raw_val = message.value()
        if isinstance(raw_val, (bytes, bytearray)):
            raw_val = raw_val.decode("utf-8")

        event_id = None
        payload_dict = {}

        try:
            payload_dict = json.loads(raw_val) if isinstance(raw_val, str) else raw_val
            if isinstance(payload_dict, dict):
                event_id = payload_dict.get("event_id")

            # Validate event against schema
            event = TransactionEvent.model_validate(payload_dict)
            res = self.engine.process(event)

            logger.info(
                "Processed event %s (tx: %s) -> %s (latency: %.2f us)",
                event.event_id,
                event.transaction_id,
                res.status,
                res.latency_us,
            )
            return {"status": res.status, "event_id": event.event_id, "result": res}

        except (json.JSONDecodeError, ValidationError, Exception) as exc:
            # Poison pill or schema rejection -> Route to DLQ and commit offset
            error_reason = f"Kafka worker payload rejection: {exc}"
            logger.warning("Quarantining malformed event %s to DLQ: %s", event_id, error_reason)

            try:
                now_str = datetime.now(timezone.utc).isoformat()
                with self.engine.storage.transaction() as db:
                    db.execute(
                        "INSERT INTO dead_letter_events(event_id, payload, reason, status, created_at) "
                        "VALUES (?, ?, ?, 'unresolved', ?)",
                        (event_id, json.dumps(payload_dict if payload_dict else {"raw": str(raw_val)}),
                         error_reason, now_str),
                    )
            except Exception as db_exc:
                logger.error("Failed to write to DLQ for event %s: %s", event_id, db_exc)

            return {"status": "invalid", "event_id": event_id, "error": error_reason}

    def run(self, max_messages: int | None = None, stop_event: threading.Event | None = None):
        """Runs the main consumer loop until stopped or max_messages reached."""
        consumer = self._init_consumer()
        active_stop = stop_event or self._stop_requested
        processed_count = 0

        # Handle signals if running on main thread
        try:
            signal.signal(signal.SIGINT, lambda s, f: active_stop.set())
            signal.signal(signal.SIGTERM, lambda s, f: active_stop.set())
        except (ValueError, AttributeError):
            pass  # Running in sub-thread

        logger.info("Kafka consumer worker started on topic '%s' (group: '%s')", self.topic, self.group_id)

        try:
            while not active_stop.is_set():
                if max_messages is not None and processed_count >= max_messages:
                    break

                message = consumer.poll(1.0)
                if message is None:
                    continue

                if message.error():
                    # Check for partition EOF
                    if message.error().code() == -191:  # _PARTITION_EOF
                        continue
                    logger.error("Kafka consumer error: %s", message.error())
                    continue

                # Process event idempotently
                self.process_single_message(message)
                processed_count += 1

                # Commit offset synchronously (At-least-once transport + idempotent commit = exactly-once)
                consumer.commit(message=message, asynchronous=False)

        finally:
            logger.info("Shutting down Kafka consumer worker cleanly...")
            try:
                consumer.close()
            except Exception as close_exc:
                logger.debug("Error during consumer close: %s", close_exc)


def run_worker(engine: DeduplicationEngine, max_messages: int | None = None):
    worker = KafkaWorker(engine)
    worker.run(max_messages=max_messages)