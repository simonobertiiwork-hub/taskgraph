# ADR-007: Event Streaming with Apache Kafka

## Context

Need a platform for publishing and storing application events.

Asynchronous messaging systems such as RabbitMQ are suitable for task processing, but event streams require durable storage and replay capability.

## Decision

Use:
- Apache Kafka
- Kafka UI

Implement:
- Event publishing
- Topic-based communication
- Event inspection through Kafka UI

## Alternatives

- RabbitMQ only
- Direct service-to-service communication
- Database polling

## Why

- Industry-standard event streaming platform
- Durable event storage
- Supports event-driven architecture
- Allows replaying historical events

## Tradeoff

- Additional infrastructure
- More complex configuration
- Requires topic and consumer management