# ADR-005: Asynchronous Processing with RabbitMQ and Celery

## Context

Need background execution for long-running operations.

## Decision

Use:

- RabbitMQ broker
- Celery workers
- Task queue pattern

## Alternatives

- FastAPI BackgroundTasks
- ThreadPoolExecutor
- Pure asyncio

## Why

- Decouples API from processing
- Improves response time
- Scales horizontally
- Industry-standard solution

## Tradeoff

- Additional infrastructure
- Queue monitoring required
- More deployment complexity