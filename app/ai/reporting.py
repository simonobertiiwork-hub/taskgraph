"""Deterministic synthesis of a grounded incident report."""

from __future__ import annotations

from typing import Any

from app.ai.errors import AIIncidentError
from app.ai.schemas import (
    IncidentAnalysisRequest,
    IncidentReportDraft,
    IndexScanMeasuredResult,
    SupportedStatement,
)


def _evidence_id(result: dict[str, Any], pointer: str) -> str:
    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        raise AIIncidentError("Tool result contains no evidence array")
    for item in evidence:
        if isinstance(item, dict) and item.get("json_pointer") == pointer:
            evidence_id = item.get("evidence_id")
            if isinstance(evidence_id, str):
                return evidence_id
    raise AIIncidentError(f"Tool evidence is missing pointer {pointer}")


def build_grounded_incident_report(
    request: IncidentAnalysisRequest,
    tool_results: dict[str, dict[str, Any]],
) -> IncidentReportDraft:
    """Build the canonical report from verified tools without generative JSON."""
    try:
        summary = tool_results["get_run_summary"]
        plans = tool_results["get_query_plan"]
        before_ms = float(summary["before_execution_time_ms"])
        after_ms = float(summary["after_execution_time_ms"])
        speedup = float(summary["speedup"])
        index_name = str(plans["index_name"])
        before_nodes = ", ".join(str(item) for item in plans["before"]["node_types"])
        after_nodes = ", ".join(str(item) for item in plans["after"]["node_types"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AIIncidentError(f"Tool results cannot build a report: {exc}") from exc

    before_node_id = _evidence_id(plans, "/before/node_types")
    before_indexes_id = _evidence_id(plans, "/before/index_names")
    after_node_id = _evidence_id(plans, "/after/node_types")
    index_name_id = _evidence_id(plans, "/index/name")
    index_definition_id = _evidence_id(plans, "/index/definition")
    before_ms_id = _evidence_id(summary, "/before/median_execution_time_ms")
    after_ms_id = _evidence_id(summary, "/after/median_execution_time_ms")
    speedup_id = _evidence_id(summary, "/comparison/speedup")

    return IncidentReportDraft(
        run_id=request.run_id,
        summary=SupportedStatement(
            text=(
                f"План изменился с {before_nodes} на {after_nodes} после добавления "
                f"индекса {index_name}."
            ),
            evidence_ids=[before_node_id, after_node_id, index_name_id],
        ),
        problem=SupportedStatement(
            text=(
                f"До изменения PostgreSQL использовал {before_nodes}, а медиана "
                f"времени выполнения составляла {before_ms} мс."
            ),
            evidence_ids=[before_node_id, before_ms_id],
        ),
        root_cause=SupportedStatement(
            text="Исходный план не использовал индекс для поиска по title.",
            evidence_ids=[before_indexes_id, index_name_id],
        ),
        applied_fix=SupportedStatement(
            text=f"Добавлен B-tree индекс {index_name} по полю title.",
            evidence_ids=[index_definition_id, index_name_id],
        ),
        result=IndexScanMeasuredResult(
            statement=SupportedStatement(
                text=(
                    f"Медиана сократилась с {before_ms} до {after_ms} мс, "
                    f"ускорение составило {speedup} раза."
                ),
                evidence_ids=[before_ms_id, after_ms_id, speedup_id],
            ),
            before_ms=before_ms,
            after_ms=after_ms,
            speedup=speedup,
        ),
        limitations=["Результат получен в локальном воспроизводимом сценарии."],
    )
