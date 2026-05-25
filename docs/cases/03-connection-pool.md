# Case #3: Connection Pool Saturation

## Problem

Async improves concurrency.

It does not remove database bottlenecks.

Configuration:

pool_size=5
max_overflow=0

Endpoint:

GET /tasks/slow

## Investigation

Load test via k6:

5 VUs
p95 ≈ 3s
0 errors

50 VUs
p95 ≈ 3.3s
0 errors

500 VUs
p95 ≈ 35s
≈76% request failures
472 interrupted iterations

Connection pool saturation observed.

## Fix

Before:

pool_size=5
max_overflow=0

After:

pool_size=20
max_overflow=20

Retested with same k6 scenario.

## Result

p95:

35s → 29s

Request failures:

76% → 0%

Connection pool stopped being the main bottleneck.

High concurrency still causes degradation.

## Lessons Learned

Async improves concurrency.

Database limits still matter.

Increasing pool size reduces saturation.

Database constraints remain bottlenecks under high concurrency.