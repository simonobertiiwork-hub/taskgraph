from app.ai.repositories.runs import FileRunRepository
from app.ai.reporting import build_grounded_incident_report
from app.ai.schemas import IncidentAnalysisRequest, RunScenario
from app.ai.tools.race_condition import RaceConditionTools
from app.ai.validation import validate_incident_report
from app.ai.graph import IncidentWorkflow
from app.ai.provider import StubLLMProvider
from app.ai.schemas import IncidentAnalysisStatus, RequestedToolCall
from app.ai.tool_registry import build_index_tool_registry
from app.ai.tools.index_scan import IndexScanTools
import pytest
from tests.unit.run_artifacts import write_race_run


def test_race_tool_and_deterministic_report_are_grounded(tmp_path):
    context = write_race_run(tmp_path)
    metrics = RaceConditionTools(FileRunRepository(tmp_path)).get_concurrency_metrics(context.run_id)
    result = {"get_concurrency_metrics": metrics.model_dump(mode="json")}
    request = IncidentAnalysisRequest(run_id=context.run_id, question="Почему произошла потеря обновления?")
    report = build_grounded_incident_report(request, result)

    assert metrics.lost_update_detected is True
    assert metrics.stale_writer_rows_updated == 0
    assert metrics.optimistic_final_version == 2
    assert report.scenario == RunScenario.RACE_CONDITION
    assert validate_incident_report(report, request, result) == []


@pytest.mark.asyncio
async def test_race_run_completes_langgraph(tmp_path):
    context = write_race_run(tmp_path)
    repository = FileRunRepository(tmp_path)
    provider = StubLLMProvider(
        tool_batches=[[RequestedToolCall(
            call_id="race-call",
            tool_name="get_concurrency_metrics",
            arguments={"run_id": str(context.run_id)},
        )]],
        json_responses=[],
    )
    workflow = IncidentWorkflow(
        provider=provider,
        tool_registry=build_index_tool_registry(
            IndexScanTools(repository), RaceConditionTools(repository)
        ),
        repository=repository,
        deterministic_report=True,
    )
    response = await workflow.analyze(
        IncidentAnalysisRequest(
            run_id=context.run_id,
            question="Почему возник lost update и как version predicate его обнаружил?",
        )
    )
    assert response.status == IncidentAnalysisStatus.COMPLETED
    assert response.validation_errors == []
    assert response.report is not None
    assert response.report.scenario == RunScenario.RACE_CONDITION
