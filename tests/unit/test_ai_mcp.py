import pytest

from app.ai.mcp_server import collect_incident_evidence, list_incident_scenarios
from app.ai.schemas import RunScenario
from demos.cases.mcp_smoke import MCPSmokeConfig, run_mcp_smoke
from tests.unit.run_artifacts import write_pool_run


def test_mcp_function_exposes_only_verified_evidence(tmp_path, monkeypatch):
    context = write_pool_run(tmp_path)
    monkeypatch.setenv("TASKGRAPH_RESULTS_DIR", str(tmp_path))
    payload = collect_incident_evidence(
        RunScenario.CONNECTION_POOL_EXHAUSTION, context.run_id
    )
    assert payload["run_id"] == str(context.run_id)
    assert set(payload["evidence"]) == {"get_pool_metrics"}
    assert list_incident_scenarios()["scenarios"] == [
        "index_scan", "race_condition", "connection_pool_exhaustion"
    ]


@pytest.mark.asyncio
async def test_mcp_stdio_transport_calls_real_server(tmp_path):
    write_pool_run(tmp_path)
    result = await run_mcp_smoke(
        MCPSmokeConfig(
            results_dir=tmp_path,
            scenario=RunScenario.CONNECTION_POOL_EXHAUSTION,
        )
    )
    assert result["passed"] is True
    assert result["tools"] == ["get_incident_evidence", "list_incident_scenarios"]
