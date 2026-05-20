# TaskGraph

Backend research project focused on reproducing and analyzing production-like backend scenarios.

## Stack

Python 3.12 • FastAPI • PostgreSQL • SQLAlchemy 2.0 (async) • asyncpg • Alembic • Docker Compose • k6 • Prometheus • Grafana

## Goal

TaskGraph reproduces production-like backend scenarios to analyze:

- system behavior
- performance bottlenecks
- latency degradation
- concurrency issues
- failure patterns

Scenarios covered:

- race conditions
- PostgreSQL query optimization
- connection pool saturation
- heavy query impact
- recursive graph traversal
- graph cycle prevention

---

## Cases

### 1. Race Condition

Optimistic locking via version field.

Result:

- concurrent updates → 409 Conflict
- prevents silent data loss

---

### 2. PostgreSQL Performance

Investigation:

- Seq Scan vs Index Scan
- selectivity behavior
- EXPLAIN ANALYZE

Result:

13.9 ms → 0.04 ms

---

### 3. Connection Pool Saturation

Configuration:

```text
pool_size=5
max_overflow=0
```

Investigation:

- connection bottlenecks
- latency growth
- concurrent load via k6

Key finding:

> async != infinite parallelism

---

### 4. Heavy Queries

Investigation:

- latency amplification
- slow SQL impact on lightweight endpoints

Result:

5–20 ms → 1.5–8.9 s

---

### 5. Recursive Graph Incident

Investigation:

- recursive CTE
- cyclic dependencies (A → B → C → A)
- recursive traversal degradation

Protection:

- cycle validation
- visited path
- depth limit

---

## Testing

Pytest:

- `test_tasks.py`
- `test_graph.py`
- `test_security.py`

Performance:

- `k6.js`
- `k6-stages.js`
- `k6-multi.js`

Manual investigation:

- `test_pool.py`
- `test_heavy.py`

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

API:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

---

## Load Testing

```bash
k6 run k6.js
```

---

## Migrations

Create:

```bash
alembic revision --autogenerate -m "message"
```

Apply:

```bash
alembic upgrade head
```

---

## Documentation

Detailed case documentation:

```text
docs/cases/
```

---

## Project Philosophy

Reproduce → Measure → Understand → Fix → Verify