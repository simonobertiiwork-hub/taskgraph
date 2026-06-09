# Case #7: Async Processing with RabbitMQ and Celery

## Problem

Long-running operations block HTTP request processing.

## Investigation

Synchronous execution:
- Request waits until work completes
- API response time grows with task duration

Asynchronous execution:
- Request publishes message
- Worker processes task independently

Measured via Celery worker logs and RabbitMQ queue activity.

## Solution

Implemented asynchronous processing:
- RabbitMQ as message broker
- Celery as background worker

Flow:
FastAPI
→ RabbitMQ
→ Celery Worker
→ Result

## Result

- HTTP response returns immediately
- Background processing separated from API
- Improved system responsiveness

## Lessons Learned

- Message brokers decouple components.
- Async processing improves user experience.
- Monitoring is required for queue-based systems.