from pathlib import Path

from app.ai.repositories.runs import FileRunRepository
from app.ai.schemas import IncidentAnalysisRequest, IncidentReportDraft
from app.ai.tools.index_scan import IndexScanTools
from app.ai.validation import validate_incident_report
from tests.unit.incident_report_factory import valid_report_payload
from tests.unit.run_artifacts import write_index_run


def build_inputs(tmp_path: Path):
    context = write_index_run(tmp_path)
    tools = IndexScanTools(FileRunRepository(tmp_path))
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
    return context, request, tool_results


def test_validator_accepts_fully_grounded_report(tmp_path: Path):
    context, request, tool_results = build_inputs(tmp_path)
    report = IncidentReportDraft.model_validate(
        valid_report_payload(context.run_id, tool_results)
    )

    assert validate_incident_report(report, request, tool_results) == []


def test_validator_rejects_changed_numeric_value(tmp_path: Path):
    context, request, tool_results = build_inputs(tmp_path)
    payload = valid_report_payload(context.run_id, tool_results)
    payload["result"]["before_ms"] = 999.0
    report = IncidentReportDraft.model_validate(payload)

    errors = validate_incident_report(report, request, tool_results)

    assert any("before_ms must equal tool value" in error for error in errors)


def test_validator_rejects_unknown_evidence_id(tmp_path: Path):
    context, request, tool_results = build_inputs(tmp_path)
    payload = valid_report_payload(context.run_id, tool_results)
    payload["problem"]["evidence_ids"] = ["ev_00000000000000000000"]
    report = IncidentReportDraft.model_validate(payload)

    errors = validate_incident_report(report, request, tool_results)

    assert any("problem cites unknown evidence" in error for error in errors)
    assert any(
        "problem does not cite its required evidence" in error for error in errors
    )


def test_validator_requires_both_independent_tools(tmp_path: Path):
    context, request, tool_results = build_inputs(tmp_path)
    report = IncidentReportDraft.model_validate(
        valid_report_payload(context.run_id, tool_results)
    )
    tool_results.pop("get_query_plan")

    errors = validate_incident_report(report, request, tool_results)

    assert errors == ["Missing required tools: get_query_plan"]
