"""End-to-end LangGraph demo over verified TaskGraph evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import httpx

from app.ai.graph import IncidentWorkflow
from app.ai.provider import OpenAICompatibleLLMProvider
from app.ai.repositories.runs import FileRunRepository
from app.ai.schemas import (
    IncidentAnalysisRequest,
    IncidentAnalysisResponse,
    IncidentAnalysisStatus,
    RunScenario,
)
from app.ai.tool_registry import build_index_tool_registry
from app.ai.tools.index_scan import IndexScanTools
from app.ai.tools.race_condition import RaceConditionTools
from app.ai.rag.embeddings import HashEmbeddingProvider
from app.ai.rag.repository import PgVectorDocumentRepository
from app.ai.rag.service import RAGService
from app.core.config import Settings
from demos.common.reporting import write_json, write_text

CASE_NAME = "ai_incident_analyst"
DEFAULT_QUESTION = (
    "Почему запрос выполнялся медленно, что было причиной и какое изменение "
    "исправило проблему?"
)


@dataclass(frozen=True, slots=True)
class AIIncidentDemoConfig:
    """Runtime parameters for one live-provider analysis."""

    results_dir: Path = Path("demos/results")
    output_dir: Path = Path("demos/results")
    run_id: UUID | None = None
    question: str = DEFAULT_QUESTION
    scenario: RunScenario = RunScenario.INDEX_SCAN


def _render_report(response: IncidentAnalysisResponse) -> str:
    if response.report is None:
        errors = "\n".join(f"- {error}" for error in response.validation_errors)
        return f"""# TaskGraph AI Incident Analyst

Analysis ID: `{response.analysis_id}`
Run ID: `{response.request.run_id}`
Status: **FAILED**

## Validation errors

{errors or "- Unknown failure"}
"""

    report = response.report
    limitations = "\n".join(f"- {item}" for item in report.limitations) or "- None"
    if report.scenario == RunScenario.INDEX_SCAN:
        measured = f"- Before: `{report.result.before_ms}` ms\n- After: `{report.result.after_ms}` ms\n- Speedup: `{report.result.speedup}`x"
    else:
        measured = (
            f"- Lost update reproduced: `{report.result.lost_update_detected}`\n"
            f"- Stale writer rows updated: `{report.result.stale_writer_rows_updated}`\n"
            f"- Optimistic conflict detected: `{report.result.optimistic_conflict_detected}`\n"
            f"- Final version: `{report.result.optimistic_final_version}`"
        )
    sources = "\n".join(
        f"- `{item.source_path}` — {item.section} (score `{item.score:.3f}`)"
        for item in report.sources
    ) or "- No source exceeded the relevance threshold"
    return f"""# TaskGraph AI Incident Analyst

Analysis ID: `{response.analysis_id}`
Run ID: `{response.request.run_id}`
Status: **COMPLETED**

## Summary

{report.summary.text}

## Problem

{report.problem.text}

## Root cause

{report.root_cause.text}

## Applied fix

{report.applied_fix.text}

## Measured result

{report.result.statement.text}

{measured}

## Documentation sources

{sources}

## Limitations

{limitations}

## Validation

- Structured schema: PASS
- Evidence references: PASS
- Numeric values: PASS
- Unsupported tool names: none
"""


async def run_ai_incident_analyst(
    settings: Settings,
    config: AIIncidentDemoConfig,
) -> dict[str, object]:
    """Run tool selection, execution, report generation, and validation."""
    repository = FileRunRepository(config.results_dir)
    run = (
        repository.get(config.run_id)
        if config.run_id is not None
        else repository.latest(config.scenario)
    )
    request = IncidentAnalysisRequest(
        run_id=run.manifest.run_id,
        question=config.question,
    )
    api_key = (
        settings.llm_api_key.get_secret_value()
        if settings.llm_api_key is not None
        else None
    )

    print("TaskGraph demo: LangGraph AI Incident Analyst")
    print(f"Run ID: {request.run_id}")
    print(f"Provider: {settings.llm_provider}")
    print(f"Model: {settings.llm_model}")
    deterministic_report = settings.llm_provider.lower() == "ollama"
    print(
        "Report mode: "
        + ("deterministic-grounded" if deterministic_report else "llm-structured")
    )

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.llm_timeout_seconds),
        trust_env=settings.llm_trust_env,
    ) as http_client:
        provider = OpenAICompatibleLLMProvider(
            http_client=http_client,
            base_url=settings.llm_base_url,
            api_key=api_key,
            model=settings.llm_model,
            provider=settings.llm_provider,
            max_retries=settings.llm_max_retries,
            backoff_seconds=settings.llm_retry_backoff_seconds,
        )
        index_tools = IndexScanTools(repository)
        race_tools = RaceConditionTools(repository)
        tool_registry = build_index_tool_registry(index_tools, race_tools)
        from app.db.session import AsyncSessionLocal
        retriever = RAGService(
            PgVectorDocumentRepository(AsyncSessionLocal),
            HashEmbeddingProvider(model=settings.embedding_model, dimensions=settings.embedding_dimensions),
            top_k=settings.rag_top_k,
            threshold=settings.rag_score_threshold,
        )
        workflow = IncidentWorkflow(
            provider=provider,
            tool_registry=tool_registry,
            repository=repository,
            deterministic_report=deterministic_report,
            retriever=retriever,
        )
        response = await workflow.analyze(request)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    result_dir = (
        config.output_dir.expanduser().resolve()
        / CASE_NAME
        / f"{timestamp}_{response.analysis_id}"
    )
    result_dir.mkdir(parents=True, exist_ok=False)
    write_json(
        result_dir / "request.json",
        request.model_dump(mode="json"),
    )
    write_json(
        result_dir / "tool_calls.json",
        [item.model_dump(mode="json") for item in response.tool_calls],
    )
    write_json(
        result_dir / "provider_calls.json",
        [item.model_dump(mode="json") for item in response.provider_calls],
    )
    write_json(
        result_dir / "report.json",
        response.model_dump(mode="json"),
    )
    report_path = result_dir / "report.md"
    write_text(report_path, _render_report(response))

    print(
        "Selected tools: " + ", ".join(call.tool_name for call in response.tool_calls)
    )
    print(f"Validation errors: {len(response.validation_errors)}")
    print(f"Documentation sources: {len(response.report.sources) if response.report else 0}")
    print(f"Latency: {response.latency_ms:.3f} ms")
    return {
        "status": response.status.value,
        "analysis_id": response.analysis_id,
        "run_id": request.run_id,
        "result_dir": result_dir,
        "report_path": report_path,
        "response": response,
        "passed": response.status == IncidentAnalysisStatus.COMPLETED,
    }
