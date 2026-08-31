import json

import pytest

from app.ai.events import KafkaIncidentPublisher, build_incident_event
from app.ai.graph import IncidentWorkflow
from app.ai.provider import StubLLMProvider
from app.ai.repositories.runs import FileRunRepository
from app.ai.schemas import IncidentAnalysisRequest, RequestedToolCall, RunScenario
from app.ai.tool_registry import build_index_tool_registry
from app.ai.tools.index_scan import IndexScanTools
from tests.unit.run_artifacts import write_index_run


async def build_response(tmp_path):
    context = write_index_run(tmp_path)
    repository = FileRunRepository(tmp_path)
    registry = build_index_tool_registry(IndexScanTools(repository))
    provider = StubLLMProvider(
        tool_batches=[[
            RequestedToolCall(call_id="a", tool_name="get_run_summary", arguments={"run_id": str(context.run_id)}),
            RequestedToolCall(call_id="b", tool_name="get_query_plan", arguments={"run_id": str(context.run_id)}),
        ]],
        json_responses=[],
    )
    return await IncidentWorkflow(
        provider=provider,
        tool_registry=registry,
        repository=repository,
        deterministic_report=True,
    ).analyze(IncidentAnalysisRequest(run_id=context.run_id, question="Why was this query slow?"))


class FakeProducer:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.sent = []

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def send_and_wait(self, topic, value):
        self.sent.append((topic, value))


@pytest.mark.asyncio
async def test_kafka_event_is_versioned_and_published_once(tmp_path):
    response = await build_response(tmp_path)
    producers = []

    def factory(**kwargs):
        producer = FakeProducer(**kwargs)
        producers.append(producer)
        return producer

    event = await KafkaIncidentPublisher(
        bootstrap_servers="kafka:29092",
        topic="taskgraph.ai.incident.completed",
        producer_factory=factory,
    ).publish(response, RunScenario.INDEX_SCAN)

    producer = producers[0]
    assert producer.started and producer.stopped
    assert len(producer.sent) == 1
    assert producer.sent[0][0] == "taskgraph.ai.incident.completed"
    assert json.loads(producer.sent[0][1]) == event
    assert event["schema_version"] == 1
    assert event["scenario"] == "index_scan"
    assert "question" not in event
    assert build_incident_event(response, RunScenario.INDEX_SCAN)["selected_tools"] == [
        "get_run_summary", "get_query_plan"
    ]
