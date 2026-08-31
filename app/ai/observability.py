"""Prometheus metrics for the incident-analysis pipeline."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

from app.ai.schemas import IncidentAnalysisResponse, RunScenario

AI_ANALYSES = Counter(
    "taskgraph_ai_analyses_total",
    "Completed AI incident-analysis runs.",
    ("scenario", "status"),
)
AI_ANALYSIS_DURATION = Histogram(
    "taskgraph_ai_analysis_duration_seconds",
    "End-to-end AI incident-analysis latency.",
    ("scenario",),
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 20, 40, 80, 160, 320),
)
AI_TOOL_CALLS = Counter(
    "taskgraph_ai_tool_calls_total",
    "Grounded evidence tool calls selected by the agent.",
    ("scenario", "tool"),
)
AI_VALIDATION_ERRORS = Counter(
    "taskgraph_ai_validation_errors_total",
    "Structured-report validation errors.",
    ("scenario",),
)
AI_DOCUMENTATION_SOURCES = Histogram(
    "taskgraph_ai_documentation_sources",
    "RAG documentation sources attached to a report.",
    ("scenario",),
    buckets=(0, 1, 2, 3, 4, 5),
)
AI_KAFKA_EVENTS = Counter(
    "taskgraph_ai_kafka_events_total",
    "Incident-analysis Kafka publication attempts.",
    ("status",),
)


def record_analysis(response: IncidentAnalysisResponse, scenario: RunScenario) -> None:
    """Record one terminal analysis without exposing questions or run ids."""
    scenario_value = scenario.value
    AI_ANALYSES.labels(scenario=scenario_value, status=response.status.value).inc()
    AI_ANALYSIS_DURATION.labels(scenario=scenario_value).observe(
        response.latency_ms / 1000
    )
    for call in response.tool_calls:
        AI_TOOL_CALLS.labels(scenario=scenario_value, tool=call.tool_name).inc()
    if response.validation_errors:
        AI_VALIDATION_ERRORS.labels(scenario=scenario_value).inc(
            len(response.validation_errors)
        )
    source_count = len(response.report.sources) if response.report else 0
    AI_DOCUMENTATION_SOURCES.labels(scenario=scenario_value).observe(source_count)


def record_kafka_event(status: str) -> None:
    """Record a bounded Kafka outcome label."""
    if status not in {"published", "failed", "disabled"}:
        raise ValueError(f"Unsupported Kafka metric status: {status}")
    AI_KAFKA_EVENTS.labels(status=status).inc()
