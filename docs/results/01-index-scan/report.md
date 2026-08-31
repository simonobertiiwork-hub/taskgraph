# Case #1: PostgreSQL Seq Scan to Index Scan

Generated at: `2026-08-27T12:05:31.393433+00:00`

## Environment

- Database: `taskgraph`
- PostgreSQL: `15.18 (Debian 15.18-1.pgdg13+1)`
- Rows: `200000`
- Lookup title: `task 150000`
- Measured runs per phase: `5`

## Query

```sql
SELECT * FROM tasks WHERE title = :title
```

## Result

| Phase | Median execution time | Plan nodes | Indexes |
| --- | ---: | --- | --- |
| Before | 13.505000 ms | Seq Scan | none |
| After | 0.016000 ms | Index Scan | idx_tasks_title |

- Speedup: **844.06x**
- Execution-time reduction: **99.88%**

## Verification

| Check | Result |
| --- | --- |
| `before_uses_seq_scan` | PASS |
| `after_uses_index_plan` | PASS |
| `after_uses_expected_index` | PASS |
| `after_median_is_faster` | PASS |

Overall status: **PASSED**

Raw PostgreSQL plans are stored in `before.json` and `after.json`.
