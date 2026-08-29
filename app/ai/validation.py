"""Deterministic validation for grounded incident reports."""

from __future__ import annotations

import math
from typing import Any

from app.ai.schemas import IncidentAnalysisRequest, IncidentReportDraft, IndexScanMeasuredResult, RaceConditionMeasuredResult, RunScenario

REQUIRED_TOOLS_BY_SCENARIO = {
    RunScenario.INDEX_SCAN: {"get_run_summary", "get_query_plan"},
    RunScenario.RACE_CONDITION: {"get_concurrency_metrics"},
}
REQUIRED_TOOLS = REQUIRED_TOOLS_BY_SCENARIO[RunScenario.INDEX_SCAN]


def required_tools_for(scenario: RunScenario) -> set[str]:
    return set(REQUIRED_TOOLS_BY_SCENARIO.get(scenario, set()))


def _evidence_index(tool_results: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    evidence: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for tool_name, result in tool_results.items():
        payload = result.get("evidence")
        if not isinstance(payload, list):
            errors.append(f"{tool_name} returned no evidence array")
            continue
        for item in payload:
            if not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str):
                errors.append(f"{tool_name} returned malformed evidence")
                continue
            evidence[item["evidence_id"]] = item
    return evidence, errors


def validate_incident_report(
    report: IncidentReportDraft,
    request: IncidentAnalysisRequest,
    tool_results: dict[str, dict[str, Any]],
    retrieved_documents: list[Any] | None = None,
) -> list[str]:
    required = required_tools_for(report.scenario)
    missing = required - set(tool_results)
    if missing:
        return [f"Missing required tools: {', '.join(sorted(missing))}"]
    evidence, errors = _evidence_index(tool_results)
    if report.run_id != request.run_id:
        errors.append("Report run_id does not match request")
    statements = {
        "summary": report.summary,
        "problem": report.problem,
        "root_cause": report.root_cause,
        "applied_fix": report.applied_fix,
        "result": report.result.statement,
    }
    for field_name, statement in statements.items():
        unknown = set(statement.evidence_ids) - set(evidence)
        if unknown:
            errors.append(f"{field_name} cites unknown evidence: {', '.join(sorted(unknown))}")
    if report.scenario == RunScenario.INDEX_SCAN and isinstance(report.result, IndexScanMeasuredResult):
        source = tool_results["get_run_summary"]
        for name, actual, expected in (
            ("before_ms", report.result.before_ms, float(source["before_execution_time_ms"])),
            ("after_ms", report.result.after_ms, float(source["after_execution_time_ms"])),
            ("speedup", report.result.speedup, float(source["speedup"])),
        ):
            if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
                errors.append(f"result.{name} must equal tool value {expected!r}, got {actual!r}")
        citation_rules = {
            "problem": {key for key, item in evidence.items() if item.get("json_pointer") == "/before/node_types"},
            "root_cause": {key for key, item in evidence.items() if item.get("json_pointer") in {"/before/index_names", "/index/name"}},
            "applied_fix": {key for key, item in evidence.items() if item.get("json_pointer") in {"/index/definition", "/index/name"}},
        }
        for field_name, required_ids in citation_rules.items():
            if not set(statements[field_name].evidence_ids).intersection(required_ids):
                errors.append(f"{field_name} does not cite its required evidence")
    elif report.scenario == RunScenario.RACE_CONDITION and isinstance(report.result, RaceConditionMeasuredResult):
        source = tool_results["get_concurrency_metrics"]
        for name in ("lost_update_detected", "stale_writer_rows_updated", "optimistic_conflict_detected", "optimistic_final_version"):
            if getattr(report.result, name) != source[name]:
                errors.append(f"result.{name} must equal tool value")
    else:
        errors.append("Report scenario and result type are inconsistent")
    known_chunks = {str(item.chunk_id) for item in (retrieved_documents or [])}
    for citation in report.sources:
        if str(citation.chunk_id) not in known_chunks:
            errors.append(f"Unknown RAG citation: {citation.chunk_id}")
    return errors
