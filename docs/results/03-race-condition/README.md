# Verified Result: PostgreSQL Race Condition

This directory contains the unmodified output of one successful TaskGraph demo
run captured on `2026-08-27T12:25:59.719125+00:00`.

## Environment

- PostgreSQL: `15.18 (Debian 15.18-1.pgdg13+1)`;
- database: `taskgraph`;
- transaction isolation: `read committed`;
- temporary fixture id: `200001`;
- configured row-lock hold: `1.000 s`.

## Verified Outcomes

- last write wins reproduced a lost update after both connections read version
  `1`;
- the second pessimistic writer waited `1.009599 s` and then observed the first
  committed title;
- the stale optimistic update affected `0` rows;
- the accepted optimistic update left version `2`;
- all twelve verification checks passed.

## Artifacts

- `metadata.json` — database environment and exact run parameters;
- `summary.json` — state transitions, backend PIDs, measured lock wait, and
  verification checks;
- `report.md` — generated human-readable report.

Source archive SHA-256:

```text
569656156cc4a8895b13d68c0f80a32ee933fbf68bee9b2fb030887938a905ed
```

The captured files are committed as evidence and must not be manually edited.
