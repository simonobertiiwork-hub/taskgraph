![CI](https://github.com/simonobertiiwork-hub/taskgraph/actions/workflows/ci-cd.yml/badge.svg)
# TaskGraph

Backend research project focused on reproducing and analyzing production-like backend scenarios.

## Stack

Python 3.12 • FastAPI • PostgreSQL • SQLAlchemy 2.0 (async) • asyncpg • Alembic • Redis • RabbitMQ • Celery • Apache Kafka • Kafka UI • Docker Compose • Kubernetes • Pytest • GitHub Actions • CI/CD • k6 • Prometheus • Grafana

## Goal

TaskGraph reproduces production-like backend scenarios to investigate:
- system behavior
- performance bottlenecks
- latency degradation
- concurrency issues
- failure patterns

Project philosophy:
Reproduce → Measure → Understand → Fix → Verify

## Architecture

```text
FastAPI
├─ PostgreSQL
├─ Redis
├─ RabbitMQ
│   └─ Celery Worker
├─ Kafka
│   └─ Kafka UI
├─ Prometheus / Grafana
└─ Kubernetes Deployment
```

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

7. Event Streaming

Apache Kafka integration.

Implemented:
- Kafka broker
- Kafka UI
- Producer
- Topic-based event publishing

Result:
- events stored in Kafka topics
- event-driven communication model
- topic inspection through Kafka UI

---

8. Kubernetes Deployment

Local Kubernetes deployment.

Implemented:
- Namespace
- Deployment
- Service (NodePort)
- Pod management
- kubectl troubleshooting

Investigated:
- ErrImageNeverPull
- Service routing
- Endpoint registration

Used:
- kubectl describe
- kubectl logs
- kubectl get endpoints

Result:
- TaskGraph deployed inside Kubernetes
- Pod started successfully
- Service endpoint registered
- HTTP requests reached application through ClusterIP

Key finding:
Deployment and Service should be validated independently.

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

## CI/CD

GitHub Actions pipeline automatically:
- installs project dependencies
- creates environment variables for tests
- runs pytest test suite
- builds Docker image
- publishes Docker image to GitHub Container Registry (GHCR)

Pipeline status is displayed via CI badge at the top of this README.

Implemented using GitHub Actions and GitLab CI.

---

## Testing

- Pytest
- GitHub Actions
- GitLab CI

Performance:
- k6 load testing
- connection pool investigation

Run:
docker compose run --rm app pytest tests/ -v

---

## Run

docker compose up -d --build

Swagger:
http://localhost:8000/docs

Kafka UI:
http://localhost:8080

RabbitMQ UI:
http://localhost:15672

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