# Case #2: PostgreSQL Performance

## Problem

Queries without indexes degrade as dataset grows.

## Investigation

Dataset: 2k rows

Seq Scan: ~0.34 ms
Index Scan: ~0.13 ms

Dataset: 20k rows

Seq Scan: ~2.27 ms
Index Scan: ~0.07 ms

Dataset: 200k rows

Seq Scan: ~13.94 ms
Index Scan: ~0.04 ms

Additional investigation:

Low selectivity → Seq Scan
High selectivity → Index Scan

Measured via: EXPLAIN ANALYZE

## Solution

Indexes: idx_tasks_title, idx_tasks_status

## Result

13.9 ms → 0.04 ms

## Lessons Learned

Indexes improve performance.

Execution plans depend on selectivity and data distribution.
Indexes are not always used automatically.