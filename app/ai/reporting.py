"""Deterministic synthesis of a grounded incident report."""

from __future__ import annotations

from typing import Any

from app.ai.errors import AIIncidentError
from app.ai.schemas import (
    DocumentCitation,
    IncidentAnalysisRequest,
    IncidentReportDraft,
    IndexScanMeasuredResult,
    RaceConditionMeasuredResult,
    RunScenario,
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
    retrieved_documents: list[Any] | None = None,
) -> IncidentReportDraft:
    """Build the canonical report from verified tools without generative JSON."""
    documents = retrieved_documents or []
    if "get_concurrency_metrics" in tool_results:
        return _build_race_report(request, tool_results["get_concurrency_metrics"], documents)
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
        sources=[DocumentCitation(**item.citation_payload()) for item in documents[:5]],
        limitations=["Результат получен в локальном воспроизводимом сценарии."],
    )


def _build_race_report(request: IncidentAnalysisRequest, metrics: dict[str, Any], documents: list[Any]) -> IncidentReportDraft:
    try:
        lost = bool(metrics["lost_update_detected"])
        stale_rows = int(metrics["stale_writer_rows_updated"])
        conflict = bool(metrics["optimistic_conflict_detected"])
        version = int(metrics["optimistic_final_version"])
        wait = float(metrics["pessimistic_lock_wait_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AIIncidentError(f"Race tool result cannot build a report: {exc}") from exc
    lost_id = _evidence_id(metrics, "/verification/last_write_wins/first_write_was_lost")
    both_id = _evidence_id(metrics, "/verification/last_write_wins/both_transactions_read_original")
    wait_id = _evidence_id(metrics, "/scenarios/pessimistic_lock/transaction_b/lock_wait_seconds")
    stale_id = _evidence_id(metrics, "/scenarios/optimistic_lock/transaction_b_rows_updated")
    conflict_id = _evidence_id(metrics, "/scenarios/optimistic_lock/transaction_b_conflict_detected")
    version_id = _evidence_id(metrics, "/scenarios/optimistic_lock/final/version")
    limitations = ["Результат получен в локальном воспроизводимом сценарии."]
    if not documents:
        limitations.append("RAG не вернул документацию выше порога релевантности.")
    return IncidentReportDraft(
        run_id=request.run_id,
        scenario=RunScenario.RACE_CONDITION,
        summary=SupportedStatement(text="Сценарий воспроизвёл потерю обновления и подтвердил отклонение устаревшей записи через optimistic locking.", evidence_ids=[lost_id, conflict_id]),
        problem=SupportedStatement(text="Две транзакции прочитали исходное состояние, после чего запись первой транзакции была потеряна.", evidence_ids=[both_id, lost_id]),
        root_cause=SupportedStatement(text="Обновление выполнялось без блокировки строки и без проверки версии прочитанного состояния.", evidence_ids=[both_id, lost_id]),
        applied_fix=SupportedStatement(text=f"Проверены SELECT FOR UPDATE с ожиданием {wait:.6f} с и optimistic locking по полю version.", evidence_ids=[wait_id, stale_id]),
        result=RaceConditionMeasuredResult(
            statement=SupportedStatement(text=f"Устаревший writer обновил {stale_rows} строк, конфликт обнаружен, итоговая версия равна {version}.", evidence_ids=[stale_id, conflict_id, version_id]),
            lost_update_detected=lost,
            stale_writer_rows_updated=stale_rows,
            optimistic_conflict_detected=conflict,
            optimistic_final_version=version,
        ),
        sources=[DocumentCitation(**item.citation_payload()) for item in documents[:5]],
        limitations=limitations,
    )
