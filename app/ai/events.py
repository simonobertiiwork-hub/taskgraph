"""Kafka publication for completed incident analyses."""

from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from app.ai.schemas import IncidentAnalysisResponse, RunScenario


class AsyncProducer(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send_and_wait(self, topic: str, value: bytes) -> Any: ...


ProducerFactory = Callable[..., AsyncProducer]


def build_incident_event(
    response: IncidentAnalysisResponse,
    scenario: RunScenario,
) -> dict[str, object]:
    """Build the versioned, privacy-safe event contract."""
    return {
        "schema_version": 1,
        "event_type": "taskgraph.ai.incident.completed",
        "analysis_id": str(response.analysis_id),
        "run_id": str(response.request.run_id),
        "scenario": scenario.value,
        "status": response.status.value,
        "selected_tools": [call.tool_name for call in response.tool_calls],
        "validation_error_count": len(response.validation_errors),
        "documentation_source_count": len(response.report.sources) if response.report else 0,
        "latency_ms": round(response.latency_ms, 3),
        "occurred_at_utc": datetime.now(timezone.utc).isoformat(),
    }


@dataclass(slots=True)
class KafkaIncidentPublisher:
    bootstrap_servers: str
    topic: str
    producer_factory: ProducerFactory | None = None
    timeout_seconds: float = 15.0
    max_attempts: int = 3
    retry_delay_seconds: float = 1.5

    async def publish(
        self,
        response: IncidentAnalysisResponse,
        scenario: RunScenario,
    ) -> dict[str, object]:
        """Publish once and always close the producer."""
        if self.producer_factory is None:
            from aiokafka import AIOKafkaProducer

            factory: ProducerFactory = AIOKafkaProducer
        else:
            factory = self.producer_factory
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            producer = factory(bootstrap_servers=self.bootstrap_servers)
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    await producer.start()
                    try:
                        event = build_incident_event(response, scenario)
                        payload = json.dumps(
                            event, ensure_ascii=False, separators=(",", ":")
                        ).encode("utf-8")
                        await producer.send_and_wait(self.topic, payload)
                        return event
                    finally:
                        await producer.stop()
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    await asyncio.sleep(self.retry_delay_seconds)
        assert last_error is not None
        raise last_error
