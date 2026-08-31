import pytest
from prometheus_client import generate_latest

from app.ai.observability import record_analysis, record_kafka_event
from app.ai.schemas import RunScenario
from tests.unit.test_ai_events import build_response


@pytest.mark.asyncio
async def test_ai_metrics_are_exported(tmp_path):
    response = await build_response(tmp_path)
    record_analysis(response, RunScenario.INDEX_SCAN)
    record_kafka_event("disabled")
    payload = generate_latest().decode("utf-8")
    assert "taskgraph_ai_analyses_total" in payload
    assert "taskgraph_ai_analysis_duration_seconds" in payload
    assert 'tool="get_query_plan"' in payload
    assert 'status="disabled"' in payload
