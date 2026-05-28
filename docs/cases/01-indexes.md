# Case #1: PostgreSQL Performance

## Problem

Queries without indexes degrade as dataset grows.

## Investigation

Dataset: 2k rows
- Seq Scan: ~0.34 ms
- Index Scan: ~0.13 ms

Dataset: 20k rows
- Seq Scan: ~2.27 ms
- Index Scan: ~0.07 ms

Dataset: 200k rows
- Seq Scan: ~13.94 ms
- Index Scan: ~0.07 ms

Measured via: EXPLAIN ANALYZE

## Solution

Added index: `idx_tasks_title`

## Result

~14 ms → ~0.07 ms

## Lessons Learned

- Indexes significantly improve lookup performance.
- Query plans depend on selectivity and data distribution.
- EXPLAIN ANALYZE is required for real performance investigation.