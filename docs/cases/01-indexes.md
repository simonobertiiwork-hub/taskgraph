# Case #1: PostgreSQL Seq Scan to Index Scan

## Problem

A lookup by `tasks.title` had no supporting index. As the dataset grew,
PostgreSQL had to inspect every row to return one matching task.

## Reproduction

The case is executed by code rather than by manually copying SQL into a
database client:

```bash
docker compose exec app python -m demos index-scan --confirm-reset
```

Verified run parameters:

- PostgreSQL `15.18`;
- 200,000 deterministic task rows;
- lookup value `task 150000`;
- one warm-up and five measured runs per phase;
- `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`;
- identical lookup before and after the change.

## Before

Measured execution times:

```text
15.812 ms
13.697 ms
13.505 ms
12.862 ms
12.933 ms
```

Median: `13.505 ms`.

The plan contained:

- `Seq Scan` on `tasks`;
- `199999` rows removed by the filter;
- `1667` shared buffer hits;
- one returned row.

## Change

```sql
CREATE INDEX idx_tasks_title ON tasks(title);
ANALYZE tasks;
```

## After

Measured execution times:

```text
0.043 ms
0.021 ms
0.016 ms
0.014 ms
0.013 ms
```

Median: `0.016 ms`.

The plan contained:

- `Index Scan` using `idx_tasks_title`;
- index condition `title = 'task 150000'`;
- `4` shared buffer hits;
- one returned row.

## Verified Result

- median execution time: `13.505 ms -> 0.016 ms`;
- measured speedup in this controlled run: `844.06x`;
- shared buffer hits: `1667 -> 4`;
- plan transition: `Seq Scan -> Index Scan`.

Exact timing depends on hardware and cache state. The reproducible engineering
result is the plan transition, the reduction in touched buffers, and the set of
five raw measurements rather than a single best run.

## Evidence

The complete captured run is stored in
[`docs/results/01-index-scan`](../results/01-index-scan/README.md):

- raw plans before and after the index;
- PostgreSQL version and run parameters;
- calculated summary;
- generated report.

