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

- `manifest.json` — schema version, immutable `run_id`, status, artifact paths,
  sizes, media types, and SHA-256 digests;
- `metadata.json` — PostgreSQL version and exact run parameters;
- `before.json` — raw `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` plans;
- `after.json` — raw plans after index creation;
- `summary.json` — calculated medians and verification checks;
- `report.md` — a human-readable report generated from the measurements.

The case passes only when every pre-change plan contains `Seq Scan`, every
post-change plan uses `idx_tasks_title`, and the median execution time is lower
after index creation.

Validate the latest run through the same typed read-only tools that the AI
agent will use:

```bash
docker compose exec app python -m demos inspect-index-run
```

To inspect one exact run instead of the latest one:

```bash
docker compose exec app python -m demos inspect-index-run \
  --run-id 00000000-0000-0000-0000-000000000000
```

The command verifies artifact checksums, cross-checks the raw PostgreSQL plans
against `summary.json`, and prints the number of stable evidence references.
It does not access an LLM and does not write to the database.

## Case #2: PostgreSQL Race Condition

Run all three write strategies against one temporary task fixture:

```bash
docker compose exec app python -m demos race-condition --confirm-write
```

The command demonstrates and verifies:

1. last write wins — both transactions read the same state and one update is
   silently overwritten;
2. pessimistic locking — `SELECT FOR UPDATE` makes the second transaction wait
   and observe the first committed update;
3. optimistic locking — an atomic version predicate rejects the stale update.

The demo never truncates the table. It creates one task, restores it before
each strategy, and deletes it in a `finally` block. It refuses to run without
`--confirm-write`.

Optional lock duration:

```bash
docker compose exec app python -m demos race-condition \
  --hold-seconds 1.0 \
  --confirm-write
```

Every run creates a UTC-stamped directory under
`demos/results/race_condition/` with PostgreSQL metadata, machine-readable
verification checks, measured lock-wait time, and a generated Markdown report.
New runs use the same versioned manifest contract and receive their own UUID.

## AI Incident Analyst: LangGraph + real tool calling

Step 2 analyzes the latest versioned `index_scan` run through a bounded
LangGraph workflow. Start the local OpenAI-compatible provider and download the
small demonstration model once:

```bash
docker compose up -d ollama app
docker compose exec ollama ollama pull qwen2.5:1.5b
```

Run the agent:

```bash
docker compose exec app python -m demos ai-incident-analyst
```

The workflow:

1. validates the requested `run_id`;
2. asks the model to select allowlisted LangChain tools;
3. rejects unknown tools and attempts to access another run;
4. executes `get_run_summary` and `get_query_plan` over verified artifacts;
5. requests a JSON-Schema constrained technical report;
6. validates every evidence identifier and numeric value;
7. allows at most one repair call for a rejected report.

Every run writes `request.json`, `tool_calls.json`, `provider_calls.json`,
`report.json`, and `report.md` below
`demos/results/ai_incident_analyst/`. Ordinary tests and CI use
`StubLLMProvider` and never contact Ollama.

## Step 3: pgvector RAG + Race Condition analysis

The RAG index stores heading-aware Markdown chunks, document hashes, versions,
scenario metadata and 768-dimensional embeddings in PostgreSQL/pgvector. The
default signed feature-hash embedding is deterministic and needs no additional
model download. Re-running the command only rewrites changed documents and
removes sources that no longer exist.

```bash
docker compose build app
docker compose up -d db ollama app
docker compose exec app alembic upgrade head
docker compose exec app python -m demos rag-index
docker compose exec app python -m demos race-condition --confirm-write
docker compose exec app python -m demos ai-incident-analyst --scenario race-condition
```

The workflow calls `get_concurrency_metrics`, retrieves up to five relevant
documentation chunks, and writes their path, heading and cosine score into the
report. The final technical claims still come only from verified run evidence.

## Step 4: Connection Pool Exhaustion + 20 offline evals

```bash
docker compose exec app python -m demos pool-exhaustion --confirm-load
docker compose exec app python -m demos rag-index
docker compose exec app python -m demos ai-incident-analyst --scenario pool-exhaustion
docker compose exec app python -m demos ai-evals
```

The pool demo runs identical controlled PostgreSQL work through undersized and
correctly sized SQLAlchemy pools. It requires real pool timeouts before the
change and zero after it, without mutating application tables.

The 20-case dataset covers all three scenarios and prompt-injection-shaped
questions. Offline evals report tool-selection accuracy, completion rate and
evidence-grounding rate using `StubLLMProvider`; they never call Ollama.

## Step 5: MCP, Kafka, Prometheus and final acceptance

The MCP server uses the standard stdio transport and exposes two read-only
operations. Verify a real client/server exchange:

```bash
docker compose exec app python -m demos mcp-smoke
```

To analyze an incident and publish its versioned completion event:

```bash
docker compose up -d db ollama kafka app
docker compose exec app python -m demos ai-incident-analyst \
  --scenario pool-exhaustion \
  --publish-kafka
```

The application `/metrics` endpoint includes AI analysis, tool, validation,
RAG-source and Kafka-delivery metric families. Questions, prompts and report
text are excluded from metric labels and Kafka payloads.

Run the complete offline-first acceptance check:

```bash
docker compose exec app python -m demos final-smoke --publish-kafka
```

This command runs the fixed 20-case eval set, performs an MCP stdio exchange,
checks Prometheus registration and publishes the latest validated analysis
event. Omit `--publish-kafka` when the broker is intentionally unavailable.
