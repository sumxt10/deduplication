"""Optional real Kafka consumer; direct mode does not import Kafka at startup."""
import json
import os
from .dedup import DeduplicationEngine
from .schemas import TransactionEvent


def run_worker(engine: DeduplicationEngine):
    from confluent_kafka import Consumer
    consumer = Consumer({"bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                         "group.id": os.getenv("KAFKA_GROUP_ID", "ps15-workers"),
                         "auto.offset.reset": "earliest", "enable.auto.commit": False})
    topic = os.getenv("KAFKA_TOPIC", "financial-events")
    consumer.subscribe([topic])
    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(str(message.error()))
            engine.process(TransactionEvent.model_validate(json.loads(message.value())))
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()