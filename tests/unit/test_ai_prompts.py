import json

from app.ai.prompts import build_report_messages, compact_tool_results
from app.ai.schemas import IncidentAnalysisRequest


def test_compact_tool_results_removes_integrity_metadata():
    tool_results = {
        "get_run_summary": {
            "run_id": "00000000-0000-0000-0000-000000000001",
            "before_execution_time_ms": 13.219,
            "evidence": [
                {
                    "evidence_id": "ev_before",
                    "run_id": "00000000-0000-0000-0000-000000000001",
                    "source_type": "artifact",
                    "artifact_name": "summary.json",
                    "artifact_sha256": "a" * 64,
                    "json_pointer": "/before/median_execution_time_ms",
                    "value": 13.219,
                }
            ],
        }
    }

    compact = compact_tool_results(tool_results)

    assert compact["get_run_summary"]["evidence"] == [
        {
            "evidence_id": "ev_before",
            "json_pointer": "/before/median_execution_time_ms",
            "value": 13.219,
        }
    ]
    assert tool_results["get_run_summary"]["evidence"][0]["artifact_sha256"]


def test_report_messages_use_compact_evidence():
    request = IncidentAnalysisRequest(
        run_id="00000000-0000-0000-0000-000000000001",
        question="Why was the query slow?",
    )
    tool_results = {
        "get_query_plan": {
            "transition_verified": True,
            "evidence": [
                {
                    "evidence_id": "ev_plan",
                    "artifact_sha256": "b" * 64,
                    "artifact_name": "summary.json",
                    "source_type": "artifact",
                    "run_id": str(request.run_id),
                    "json_pointer": "/before/node_types",
                    "value": ["Seq Scan"],
                }
            ],
        }
    }

    payload = json.loads(build_report_messages(request, tool_results)[1]["content"])

    serialized = json.dumps(payload)
    assert "artifact_sha256" not in serialized
    assert "ev_plan" in serialized
