"""Deterministic validation for LLM-generated incident reports."""

from __future__ import annotations

import math
from typing import Any

from app.ai.schemas import IncidentAnalysisRequest, IncidentReportDraft

REQUIRED_TOOLS = {"get_run_summary", "get_query_plan"}


def _evidence_index(
    tool_results: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    evidence: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for tool_name, result in tool_results.items():
        payload = result.get("evidence")
        if not isinstance(payload, list):
            errors.append(f"{tool_name} returned no evidence array")
            continue
        for item in payload:
            if not isinstance(item, dict) or not isinstance(
                item.get("evidence_id"), str
            ):
                errors.append(f"{tool_name} returned malformed evidence")
                continue
            evidence_id = item["evidence_id"]
            previous = evidence.get(evidence_id)
            if previous is not None and previous != item:
                errors.append(f"Conflicting evidence payload: {evidence_id}")
                continue
            evidence[evidence_id] = item
    return evidence, errors


def _ids_for_pointer(
    evidence: dict[str, dict[str, Any]],
    pointer: str,
) -> set[str]:
    return {
        evidence_id
        for evidence_id, item in evidence.items()
        if item.get("json_pointer") == pointer
    }


def validate_incident_report(
    report: IncidentReportDraft,
    request: IncidentAnalysisRequest,
    tool_results: dict[str, dict[str, Any]],
) -> list[str]:
    """Return all blocking errors without calling another model."""
    errors: list[str] = []
    missing_tools = REQUIRED_TOOLS - set(tool_results)
    if missing_tools:
        errors.append(f"Missing required tools: {', '.join(sorted(missing_tools))}")
        return errors

    evidence, evidence_errors = _evidence_index(tool_results)
    errors.extend(evidence_errors)
    if report.run_id != request.run_id:
        errors.append("Report run_id does not match request")
    if str(report.scenario) != "index_scan":
        errors.append("Report scenario must be index_scan")

    statements = {
        "summary": report.summary,
        "problem": report.problem,
        "root_cause": report.root_cause,
        "applied_fix": report.applied_fix,
        "result": report.result.statement,
    }
    known_ids = set(evidence)
    for field_name, statement in statements.items():
        unknown = set(statement.evidence_ids) - known_ids
        if unknown:
            errors.append(
                f"{field_name} cites unknown evidence: {', '.join(sorted(unknown))}"
            )

    summary_result = tool_results["get_run_summary"]
    try:
        expected_before = float(summary_result["before_execution_time_ms"])
        expected_after = float(summary_result["after_execution_time_ms"])
        expected_speedup = float(summary_result["speedup"])
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"get_run_summary has invalid numeric fields: {exc}")
        return errors

    comparisons = (
        ("before_ms", report.result.before_ms, expected_before),
        ("after_ms", report.result.after_ms, expected_after),
        ("speedup", report.result.speedup, expected_speedup),
    )
    for field_name, actual, expected in comparisons:
        if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
            errors.append(
                f"result.{field_name} must equal tool value {expected!r}, got {actual!r}"
            )

    citation_rules = {
        "problem": _ids_for_pointer(evidence, "/before/node_types"),
        "root_cause": (
            _ids_for_pointer(evidence, "/before/index_names")
            | _ids_for_pointer(evidence, "/index/name")
        ),
        "applied_fix": (
            _ids_for_pointer(evidence, "/index/definition")
            | _ids_for_pointer(evidence, "/index/name")
        ),
    }
    for field_name, required_ids in citation_rules.items():
        cited = set(statements[field_name].evidence_ids)
        if not cited.intersection(required_ids):
            errors.append(f"{field_name} does not cite its required evidence")

    numeric_ids = (
        _ids_for_pointer(evidence, "/before/median_execution_time_ms")
        | _ids_for_pointer(evidence, "/after/median_execution_time_ms")
        | _ids_for_pointer(evidence, "/comparison/speedup")
    )
    if not numeric_ids.issubset(set(report.result.statement.evidence_ids)):
        errors.append("result statement must cite before, after, and speedup evidence")
    return errors
