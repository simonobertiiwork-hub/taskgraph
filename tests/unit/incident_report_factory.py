"""Build a valid report from deterministic tool outputs for tests."""

from __future__ import annotations

from typing import Any
from uuid import UUID


def _evidence_id(tool_result: dict[str, Any], pointer: str) -> str:
    return next(
        item["evidence_id"]
        for item in tool_result["evidence"]
        if item["json_pointer"] == pointer
    )


def valid_report_payload(
    run_id: UUID,
    tool_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    summary = tool_results["get_run_summary"]
    plans = tool_results["get_query_plan"]
    before_nodes = _evidence_id(plans, "/before/node_types")
    before_indexes = _evidence_id(plans, "/before/index_names")
    index_name = _evidence_id(plans, "/index/name")
    index_definition = _evidence_id(plans, "/index/definition")
    before_ms = _evidence_id(summary, "/before/median_execution_time_ms")
    after_ms = _evidence_id(summary, "/after/median_execution_time_ms")
    speedup = _evidence_id(summary, "/comparison/speedup")
    result_evidence = [before_ms, after_ms, speedup]
    return {
        "run_id": str(run_id),
        "scenario": "index_scan",
        "summary": {
            "text": "План запроса изменился после добавления индекса.",
            "evidence_ids": [before_nodes, index_name, before_ms, after_ms],
        },
        "problem": {
            "text": "До изменения PostgreSQL использовал Seq Scan.",
            "evidence_ids": [before_nodes],
        },
        "root_cause": {
            "text": "В исходном плане не использовался индекс по title.",
            "evidence_ids": [before_indexes, index_name],
        },
        "applied_fix": {
            "text": "Добавлен B-tree индекс idx_tasks_title.",
            "evidence_ids": [index_definition],
        },
        "result": {
            "statement": {
                "text": "Медиана времени выполнения уменьшилась после изменения.",
                "evidence_ids": result_evidence,
            },
            "before_ms": summary["before_execution_time_ms"],
            "after_ms": summary["after_execution_time_ms"],
            "speedup": summary["speedup"],
        },
        "limitations": ["Результат получен в локальном воспроизводимом сценарии."],
    }
