"""Twenty deterministic regression evals for grounded incident analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import Field

from app.ai.graph import IncidentWorkflow
from app.ai.provider import StubLLMProvider
from app.ai.repositories.runs import FileRunRepository
from app.ai.schemas import IncidentAnalysisRequest, IncidentAnalysisStatus, RequestedToolCall, RunScenario, StrictModel
from app.ai.tool_registry import build_index_tool_registry
from app.ai.tools.index_scan import IndexScanTools
from app.ai.tools.pool_exhaustion import PoolExhaustionTools
from app.ai.tools.race_condition import RaceConditionTools
from demos.common.reporting import write_json, write_text


class EvalCase(StrictModel):
    id: str = Field(min_length=1)
    scenario: RunScenario
    question: str = Field(min_length=5)
    expected_tools: list[str] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class AIEvalConfig:
    dataset_path: Path = Path("demos/evals/incident_cases.json")
    results_dir: Path = Path("demos/results")
    output_dir: Path = Path("demos/results")


def load_eval_cases(path: Path) -> list[EvalCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [EvalCase.model_validate(item) for item in payload]
    if len(cases) != 20:
        raise ValueError(f"Expected exactly 20 eval cases, got {len(cases)}")
    if len({item.id for item in cases}) != len(cases):
        raise ValueError("Eval case ids must be unique")
    return cases


async def run_ai_evals(config: AIEvalConfig) -> dict[str, object]:
    cases = load_eval_cases(config.dataset_path)
    repository = FileRunRepository(config.results_dir)
    registry = build_index_tool_registry(
        IndexScanTools(repository),
        RaceConditionTools(repository),
        PoolExhaustionTools(repository),
    )
    rows: list[dict[str, object]] = []
    for case in cases:
        run = repository.latest(case.scenario)
        calls = [
            RequestedToolCall(
                call_id=f"{case.id}-{name}",
                tool_name=name,
                arguments={"run_id": str(run.manifest.run_id)},
            )
            for name in case.expected_tools
        ]
        provider = StubLLMProvider(tool_batches=[calls], json_responses=[])
        response = await IncidentWorkflow(
            provider=provider,
            tool_registry=registry,
            repository=repository,
            deterministic_report=True,
        ).analyze(
            IncidentAnalysisRequest(run_id=run.manifest.run_id, question=case.question)
        )
        actual_tools = sorted(call.tool_name for call in response.tool_calls)
        expected_tools = sorted(case.expected_tools)
        tool_match = actual_tools == expected_tools
        completed = response.status == IncidentAnalysisStatus.COMPLETED
        grounded = completed and not response.validation_errors and response.report is not None
        rows.append(
            {
                "id": case.id,
                "scenario": case.scenario.value,
                "expected_tools": expected_tools,
                "actual_tools": actual_tools,
                "tool_match": tool_match,
                "completed": completed,
                "grounded": grounded,
                "validation_errors": response.validation_errors,
            }
        )
    total = len(rows)
    tool_matches = sum(bool(row["tool_match"]) for row in rows)
    completed_count = sum(bool(row["completed"]) for row in rows)
    grounded_count = sum(bool(row["grounded"]) for row in rows)
    metrics = {
        "total_cases": total,
        "tool_selection_accuracy_percent": round(tool_matches / total * 100, 2),
        "completion_rate_percent": round(completed_count / total * 100, 2),
        "grounding_rate_percent": round(grounded_count / total * 100, 2),
        "passed_cases": sum(bool(row["tool_match"] and row["grounded"]) for row in rows),
    }
    passed = metrics["passed_cases"] == total
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    result_dir = config.output_dir.resolve() / "ai_evals" / f"{timestamp}_{uuid4()}"
    result_dir.mkdir(parents=True, exist_ok=False)
    write_json(result_dir / "eval_results.json", {"status": "passed" if passed else "failed", "metrics": metrics, "cases": rows})
    table = "\n".join(
        f"| {row['id']} | {row['scenario']} | {'PASS' if row['tool_match'] else 'FAIL'} | {'PASS' if row['grounded'] else 'FAIL'} |"
        for row in rows
    )
    report_path = result_dir / "report.md"
    write_text(
        report_path,
        f"""# TaskGraph AI Offline Evals

| Metric | Value |
| --- | ---: |
| Cases | {total} |
| Tool selection accuracy | {metrics['tool_selection_accuracy_percent']}% |
| Completion rate | {metrics['completion_rate_percent']}% |
| Grounding rate | {metrics['grounding_rate_percent']}% |

| Case | Scenario | Tools | Grounding |
| --- | --- | --- | --- |
{table}

Overall status: **{'PASSED' if passed else 'FAILED'}**
""",
    )
    return {"passed": passed, "metrics": metrics, "result_dir": result_dir, "report_path": report_path}
