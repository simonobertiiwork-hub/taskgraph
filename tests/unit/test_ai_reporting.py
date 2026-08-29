from pathlib import Path

from app.ai.reporting import build_grounded_incident_report
from app.ai.repositories.runs import FileRunRepository
from app.ai.schemas import IncidentAnalysisRequest
from app.ai.tools.index_scan import IndexScanTools
from app.ai.validation import validate_incident_report
from tests.unit.run_artifacts import write_index_run


def test_deterministic_report_is_fully_grounded(tmp_path: Path):
    context = write_index_run(tmp_path)
    repository = FileRunRepository(tmp_path)
    tools = IndexScanTools(repository)
    tool_results = {
        "get_run_summary": tools.get_run_summary(context.run_id).model_dump(
            mode="json"
        ),
        "get_query_plan": tools.get_query_plan(context.run_id).model_dump(mode="json"),
    }
    request = IncidentAnalysisRequest(
        run_id=context.run_id,
        question="Почему запрос выполнялся медленно?",
    )

    report = build_grounded_incident_report(request, tool_results)

    assert validate_incident_report(report, request, tool_results) == []
    assert (
        report.result.before_ms
        == tool_results["get_run_summary"]["before_execution_time_ms"]
    )
    assert (
        report.result.after_ms
        == tool_results["get_run_summary"]["after_execution_time_ms"]
    )
