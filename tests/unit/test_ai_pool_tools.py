import pytest

from app.ai.graph import IncidentWorkflow
from app.ai.provider import StubLLMProvider
from app.ai.repositories.runs import FileRunRepository
from app.ai.reporting import build_grounded_incident_report
from app.ai.schemas import IncidentAnalysisRequest, IncidentAnalysisStatus, RequestedToolCall, RunScenario
from app.ai.tool_registry import build_index_tool_registry
from app.ai.tools.index_scan import IndexScanTools
from app.ai.tools.pool_exhaustion import PoolExhaustionTools
from app.ai.tools.race_condition import RaceConditionTools
from app.ai.validation import validate_incident_report
from tests.unit.run_artifacts import write_pool_run


def test_pool_tool_and_report_are_grounded(tmp_path):
    context = write_pool_run(tmp_path)
    repository = FileRunRepository(tmp_path)
    metrics = PoolExhaustionTools(repository).get_pool_metrics(context.run_id)
    results = {"get_pool_metrics": metrics.model_dump(mode="json")}
    request = IncidentAnalysisRequest(run_id=context.run_id, question="Почему пул соединений исчерпался?")
    report = build_grounded_incident_report(request, results)
    assert metrics.before_pool_timeouts == 3
    assert metrics.after_pool_timeouts == 0
    assert report.scenario == RunScenario.CONNECTION_POOL_EXHAUSTION
    assert validate_incident_report(report, request, results) == []


@pytest.mark.asyncio
async def test_pool_run_completes_langgraph(tmp_path):
    context = write_pool_run(tmp_path)
    repository = FileRunRepository(tmp_path)
    provider = StubLLMProvider(
        tool_batches=[[RequestedToolCall(
            call_id="pool-call",
            tool_name="get_pool_metrics",
            arguments={"run_id": str(context.run_id)},
        )]],
        json_responses=[],
    )
    workflow = IncidentWorkflow(
        provider=provider,
        tool_registry=build_index_tool_registry(
            IndexScanTools(repository), RaceConditionTools(repository), PoolExhaustionTools(repository)
        ),
        repository=repository,
        deterministic_report=True,
    )
    response = await workflow.analyze(
        IncidentAnalysisRequest(
            run_id=context.run_id,
            question="Почему возник connection pool timeout и что изменилось после увеличения pool_size?",
        )
    )
    assert response.status == IncidentAnalysisStatus.COMPLETED
    assert response.validation_errors == []
