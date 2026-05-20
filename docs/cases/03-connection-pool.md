# Case #3: Connection Pool Saturation

## Problem

Async does not remove database bottlenecks.

Connection pool limits affect throughput.

Configuration: pool_size=5, max_overflow=0

Endpoint: GET /tasks/slow

## Investigation

10 VUs → p95 ≈ 3.0 s, 0 errors
100 VUs → p95 ≈ 3.3 s, 0 errors
1000 VUs → 14.5% errors, p95 ≈ 4.1 s

Measured via: k6

## Result

Low and medium load remained stable.

Extreme concurrency caused failures and latency growth.

## Lessons Learned

Async improves concurrency.

It does not remove database limits.