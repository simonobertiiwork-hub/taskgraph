# Case #3: Connection Pool Exhaustion

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