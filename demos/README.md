# TaskGraph Demos

This directory contains reproducible engineering demonstrations. A demo is not
an automated regression test: it prepares a controlled dataset, captures raw
measurements, applies one change, repeats the same measurement, and writes an
evidence report.

## Prerequisites

Start PostgreSQL and the application container, then apply migrations:

```bash
docker compose up -d db app
docker compose exec app alembic upgrade head
```

## Case #1: PostgreSQL Seq Scan to Index Scan

Run the case inside the application container:

```bash
docker compose exec app python -m demos index-scan --confirm-reset
```

The command deliberately truncates only the `tasks` table. It refuses to run
without `--confirm-reset` and always prints a password-safe database URL before
changing data.

Optional parameters:

```bash
docker compose exec app python -m demos index-scan \
  --rows 200000 \
  --target 150000 \
  --runs 5 \
  --confirm-reset
```

Every run creates a UTC-stamped directory under `demos/results/index_scan/`
with:

- `metadata.json` — PostgreSQL version and exact run parameters;
- `before.json` — raw `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` plans;
- `after.json` — raw plans after index creation;
- `summary.json` — calculated medians and verification checks;
- `report.md` — a human-readable report generated from the measurements.

The case passes only when every pre-change plan contains `Seq Scan`, every
post-change plan uses `idx_tasks_title`, and the median execution time is lower
after index creation.

