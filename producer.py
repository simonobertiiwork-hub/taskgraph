from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

producer.send(
    "task-events",
    {
        "event_type": "task_created",
        "task_id": 1,
        "title": "Kafka training"
    }
)

producer.flush()

print("Message sent")