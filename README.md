# TaskGraph

Production-like backend project focused on:

- PostgreSQL performance
- async SQLAlchemy
- connection pool behavior
- production incident reproduction

---

## About

TaskGraph is a backend project created to reproduce and investigate real production-like problems:

- race conditions
- heavy queries
- connection pool saturation
- recursive graph traversal
- graph cycles
- latency degradation

The project focuses on:

- system behavior
- diagnostics
- performance analysis
- prevention strategies

---

## Stack

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy 2.0 (async)
- asyncpg
- Alembic
- Docker Compose
- k6

---

## Architecture

Main components:

- async FastAPI application
- PostgreSQL database
- async SQLAlchemy session layer
- graph traversal via recursive CTE
- connection pool: `pool_size=5`, `max_overflow=0`
- latency degradation scenarios

---

## Project Structure

app/
├── db/
├── models/
├── schemas/
├── routers/
├── services/
├── repositories/

docs/
├── cases/

alembic/

---

## Cases

### Case #1 - Race Condition

Demonstration of concurrent update conflicts and optimistic locking via version field.
Conflict → 409 Conflict instead of data loss.

### Case #2 - PostgreSQL Indexes

Demonstration of:

- Seq Scan vs Index Scan (13.9 ms → 0.04 ms)
- selectivity (low vs high)
- latency difference
- EXPLAIN ANALYZE

### Case #3 - Connection Pool Saturation

Demonstration of:

- async != infinite parallelism
- limited connection pool (`pool_size=5`, `max_overflow=0`)
- latency growth under load
- k6 load testing, p95

### Case #4 - Heavy Queries

Demonstration of:

- system degradation
- latency amplification (lightweight requests: 5–20 ms → 1.5–8.9 s)
- impact of heavy queries on lightweight endpoints

### Case #5 - Recursive Graph Incident

Demonstration of:
- recursive graph traversal
- cyclic dependencies (A → B → C → A)
- infinite recursive queries
- `pg_stat_activity` diagnostics
- cycle prevention: validation + depth limit (`max_depth=20`)

---

## Results

Examples reproduced in the project:

- lightweight queries degraded from milliseconds to seconds
- recursive graph cycles caused infinite traversal
- heavy queries saturated connection pool
- latency growth under concurrent load
- PostgreSQL query plan differences

---

## Run

```bash
docker compose up -d --build
```

Application: http://localhost:8000
Swagger UI: http://localhost:8000/docs

---

## Alembic

Create migration:

```bash
docker compose run --rm app alembic revision --autogenerate -m "message"
```

Apply migrations:

```bash
docker compose run --rm app alembic upgrade head
```

⚠️ Important: Alembic Migration Bootstrap
If you need to recreate the tasks table migration from scratch, deleting the volume is the last resort.

First, check current migration status:

```bash
docker compose run --rm app alembic current
docker compose run --rm app alembic history
```

Only if the bootstrap migration is broken, proceed with volume removal:

```bash
docker compose down
docker volume rm taskgraph_postgres_data   # ⚠️ This deletes ALL database data!
docker compose up -d
docker compose run --rm app alembic revision --autogenerate -m "bootstrap tasks table"
docker compose run --rm app alembic upgrade head
```

⚠️ Warning: This will delete all existing data in the database. Use only when absolutely necessary.

## Load Testing

```bash
k6 run k6.js
```

## Goal

The goal of the project is not to build
a production-ready platform,
but to reproduce and investigate
real backend engineering problems.

## Documentation

Detailed case documentation: [docs/cases/](docs/cases)


