# AI Incident Analyst: run contract and grounded tools

Step 1 establishes the evidence boundary used by the future LangGraph agent.
No LLM is involved yet.

## Run contract

Every new demonstration run receives a UUID and writes `manifest.json` only
after its evidence files are complete. Schema version 1 records:

- scenario and terminal status;
- UTC start and completion timestamps;
- allowlisted artifact paths;
- byte sizes, media types, and SHA-256 checksums.

The manifest is the only entry point accepted by the AI repository. Files are
resolved below their owning run directory, checked for path traversal, and
verified before they are read.

## Read-only tools

`IndexScanTools` exposes two deterministic methods:

- `get_run_summary(run_id)` returns dataset size, measured before/after times,
  calculated improvement, and the applied index;
- `get_query_plan(run_id)` reads the raw `EXPLAIN (ANALYZE, BUFFERS, FORMAT
  JSON)` artifacts and verifies their plan nodes against `summary.json`.

Each normalized fact carries a stable evidence identifier, artifact digest,
and JSON Pointer. This lets the report validator in the next step reject
numbers or claims that do not originate from a verified tool result.

## Verification

After producing an index-scan run, execute:

```bash
python -m demos inspect-index-run
```

The command is successful only when the run passed and the raw evidence proves
the `Seq Scan` to index-plan transition.
