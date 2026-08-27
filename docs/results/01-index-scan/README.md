# Verified Result: PostgreSQL Index Scan

This directory contains the unmodified output of one successful TaskGraph demo
run captured on `2026-08-27T12:05:31.393433+00:00`.

## Environment

- PostgreSQL: `15.18 (Debian 15.18-1.pgdg13+1)`;
- database: `taskgraph`;
- rows: `200000`;
- measured runs per phase: `5`;
- warm-up runs per phase: `1`.

## Artifacts

- `metadata.json` — environment and exact experiment parameters;
- `before.json` — five raw sequential-scan plans;
- `after.json` — five raw index-scan plans;
- `summary.json` — medians and automated verification;
- `report.md` — generated human-readable report.

Source archive SHA-256:

```text
46f4eb7c8b15f02ffe733803cb7efa3b58e1b085de1737cf31b0c4b3d1a70ad4
```

The raw JSON files are committed as evidence and must not be manually edited.

