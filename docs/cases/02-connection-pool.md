# Case #2: Connection Pool Exhaustion

## Reproducible agent demo

The current code-first demonstration uses two temporary SQLAlchemy async
engines and the same controlled PostgreSQL workload in both phases:

- concurrency: 5;
- each connection runs `SELECT pg_sleep(0.35)`;
- `max_overflow=0`;
- `pool_timeout=0.20` seconds;
- before: `pool_size=2`;
- after: `pool_size=5`.

The before phase must produce real `sqlalchemy.exc.TimeoutError` outcomes. The
after phase must complete the same five requests without a pool timeout. Every
request result, measured wait and verification check is written below
`demos/results/connection_pool_exhaustion/` and protected by manifest checksums.

```bash
docker compose exec app python -m demos pool-exhaustion --confirm-load
docker compose exec app python -m demos ai-incident-analyst --scenario pool-exhaustion
```

The historical k6 experiment is retained below as engineering context; its
numbers are not substituted for the current reproducible run.

## Problem

Database connection pool became saturated under load.

Initial config:
pool_size=5
max_overflow=0

Endpoint:
GET /tasks/slow

## Investigation

k6 load test:

5 VUs:
- p95 ≈ 3s
- 0 failures

50 VUs:
- p95 ≈ 3.3s
- 0 failures

500 VUs:
- p95 ≈ 35s
- ~76% failures

Connection pool exhaustion reproduced.

## Solution

Before:
pool_size=5
max_overflow=0

After:
pool_size=20
max_overflow=20

Repeated the same load test.

## Result

- connection failures disappeared
- pool saturation stopped being primary bottleneck
- p95 improved: 35s → 29s

High latency under heavy load still remained.

## Lessons Learned

- Async does not remove DB bottlenecks.
- Pool configuration affects stability and latency.
- Removing one bottleneck exposes the next limitation.
