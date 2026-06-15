# Case #8: Event Streaming with Apache Kafka

## Problem

Modern distributed systems often require event-based communication between services.

Direct integration increases coupling and makes scaling more difficult.

## Investigation

Traditional communication:
- Direct service calls
- Tight coupling between components

Event streaming:
- Producer publishes event
- Kafka stores event in topic
- Consumers process events independently

Measured through Kafka UI and topic inspection.

## Solution

Implemented event streaming:
- Apache Kafka broker
- Kafka UI
- Producer application
- Topic: task-events

Flow:
Producer
→ Kafka Topic
→ Kafka UI / Consumers

## Result

- Events stored in Kafka
- Decoupled communication model
- Event history available through topics
- Infrastructure prepared for future consumers

## Lessons Learned

- Kafka is designed for event streaming rather than task execution.
- Topics provide durable event storage.
- Event-driven systems reduce service coupling.
- Listener and networking configuration are critical for containerized deployments.