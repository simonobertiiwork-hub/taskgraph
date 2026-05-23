# TaskGraph

Backend research project focused on reproducing and analyzing production-like backend scenarios.

## Stack

Python 3.12 • FastAPI • PostgreSQL • SQLAlchemy 2.0 (async) • asyncpg • Alembic • Docker Compose • k6 • Prometheus • Grafana

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

### 1. Race Condition

Optimistic locking via version field.

Result:

- concurrent updates → 409 Conflict
- prevents silent data loss

---

### 2. PostgreSQL Performance

Seq Scan vs Index Scan.

Result:

13.9 ms → 0.04 ms

Investigation:

- selectivity
- EXPLAIN ANALYZE

---

### 3. Connection Pool Saturation

Configuration:

```text
pool_size=5
max_overflow=0
```

Load testing:

- k6
- Prometheus
- Grafana
- p95

Key finding:

async != infinite parallelism

---

### 4. Heavy Queries

Heavy SQL affects lightweight requests.

Result:

5–20 ms → 1.5–8.9 s

---

### 5. Recursive Graph Incident

Recursive CTE.

Protection:

- cycle validation
- depth limit
- visited path

---

## Testing

Pytest

Performance:

- k6
- k6-multi.js

Run:

```bash
docker compose run --rm app pytest tests/ -v
```

---

## Architecture

```text
FastAPI
   ↓
API Layer
   ↓
SQLAlchemy Async
   ↓
PostgreSQL
   ↓
Prometheus / Grafana
```

---

## Run

```bash
docker compose up -d --build
```

Swagger:

```text
http://localhost:8000/docs
```

---

## Documentation

Detailed case documentation:

```text
docs/cases/
```