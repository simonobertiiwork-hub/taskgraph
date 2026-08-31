# AI Incident Analyst: LangGraph and tool calling

Step 2 adds the first complete model-backed vertical slice for `index_scan`.

## Graph

The graph contains six explicit nodes:

1. `validate_request` resolves the versioned run;
2. `plan_tools` sends OpenAI-compatible function definitions to the model;
3. `execute_tools` enforces the allowlist and matching `run_id`;
4. `generate_report` requests strict structured output;
5. `validate_report` checks citations and exact numeric values;
6. `repair_report` performs at most one correction pass.

Conditional edges allow one additional planning attempt when a required tool
is missing and one repair attempt when the deterministic validator rejects the
report. Both loops are bounded.

## Grounding boundary

The model cannot query PostgreSQL, read arbitrary files, or construct SQL. It
can select only `get_run_summary` and `get_query_plan`. LangChain generates the
OpenAI function schemas from strict Pydantic arguments, while the registry
executes only exact allowlisted names.

The final report is published only when:

- both tools were executed for the requested run;
- all cited `evidence_id` values exist in tool output;
- problem, root cause, and fix cite their required evidence categories;
- before time, after time, and speedup exactly match `get_run_summary`;
- the Pydantic structured-output schema is valid.

For the local Ollama demo, the model selects the tools and the report is then
assembled deterministically from their verified evidence. This avoids fragile
large JSON generations on small local models. Other compatible providers keep
the structured LLM report path. Both modes use the same final validator.

## Provider and offline tests

`OpenAICompatibleLLMProvider` supports live Ollama or another compatible API,
bounded retry for transport/429/5xx errors, timeout through `httpx`, provider
request IDs, and token usage. `StubLLMProvider` supplies deterministic tool
calls and reports for ordinary tests, so CI never requires a model or network.
