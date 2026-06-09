# TaskGraph

Backend research project focused on reproducing and analyzing production-like backend scenarios.

## Stack

Python 3.12 • FastAPI • PostgreSQL • SQLAlchemy 2.0 (async) • asyncpg • Alembic • Redis • RabbitMQ • Celery • Docker Compose • k6 • Prometheus • Grafana

## Goal

TaskGraph reproduces production-like backend scenarios to investigate:
- system behavior
- performance bottlenecks
- latency degradation
- concurrency issues
- failure patterns

Project philosophy:
Reproduce → Measure → Understand → Fix → Verify

---

## Cases

1. PostgreSQL Performance

Seq Scan vs Index Scan.

Result:
13.9 ms → 0.07 ms

Investigation:
- selectivity
- EXPLAIN ANALYZE

---

2. Connection Pool Exhaustion

Before:
pool_size=5
max_overflow=0

After:
pool_size=20
max_overflow=20

Load testing:
- k6
- Prometheus
- Grafana

Result:
p95: 35s → 29s

failures: 76% → 0%

Key finding:
async != infinite parallelism

---

3. Race Condition

Lost Update reproduction.

Implemented:
- Last Write Wins
- Pessimistic Locking
- Optimistic Locking

Result:
- concurrent updates → 409 Conflict
- prevents silent data loss

---

4. Recursive Graph Traversal

Recursive CTE traversal.

Protection:
- depth limit

Result:
11 ms → 0.2 ms

---

5. Redis Cache

Cache Aside Pattern.

Implemented:
- Redis cache
- TTL expiration
- cache hit / cache miss flow

Result:
- reduced PostgreSQL load
- faster repeated requests

---

6. Async Processing

RabbitMQ + Celery integration.

Implemented:
- message broker
- background workers
- asynchronous task execution

Result:
- immediate HTTP response
- background task processing
- decoupled architecture

---

## Monitoring

TaskGraph includes:

- Prometheus
- Grafana
- custom FastAPI metrics
- k6 load testing

Used for:

- request count
- latency visualization
- load investigation

---

## Testing

Pytest

Performance:
- k6 load testing
- connection pool investigation

Run:
docker compose run --rm app pytest tests/ -v

---

## Architecture

FastAPI
├─ PostgreSQL
├─ Redis
├─ RabbitMQ
│   └─ Celery Worker
└─ Prometheus / Grafana

---

## Run

docker compose up -d --build

Swagger:
http://localhost:8000/docs

Prometheus:
http://localhost:9090

Grafana:
http://localhost:3000

---

## Documentation

Detailed case documentation:
docs/cases/

Architecture decisions:
docs/adr/

Research materials:
research/