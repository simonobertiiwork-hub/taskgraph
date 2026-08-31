# Step 5 — final AI integration

This package completes the TaskGraph AI portfolio case with:

- MCP 1.26 stdio server and a real client/server smoke test;
- versioned Kafka event after a validated incident analysis;
- Prometheus metrics for analyses, tools, validation, RAG and Kafka delivery;
- an explicit offline AI/MCP gate in GitHub Actions;
- one final acceptance command;
- final architecture documentation and defensible resume wording.

## Run after extracting the archive

```bat
docker compose build app
docker compose up -d db ollama kafka app
docker compose exec app python -m pytest -q
docker compose exec app python -m demos final-smoke --publish-kafka
git status --short
```

The final command does not call Ollama. It runs 20 deterministic offline evals,
opens a real MCP stdio client/server session, checks Prometheus metric families
and publishes the latest already-validated AI analysis event to Kafka.

Expected ending:

```text
offline_eval_cases: 20
tool_selection_accuracy_percent: 100.0
grounding_rate_percent: 100.0
mcp_stdio_transport: passed
prometheus_metrics: passed
kafka_event: published
Result: PASSED
```

If Kafka is intentionally not running, omit `--publish-kafka`; the remaining
acceptance checks still run and the report records `kafka_event: skipped`.
