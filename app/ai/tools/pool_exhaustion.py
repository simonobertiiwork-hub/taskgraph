"""Grounded tool for the reproducible connection-pool demonstration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.ai.repositories.runs import FileRunRepository, InvalidRunArtifactError
from app.ai.schemas import PoolExhaustionMetrics, RunScenario
from app.ai.tools.index_scan import _evidence


def _path(payload: dict[str, Any], *parts: str) -> Any:
    current: Any = payload
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            raise InvalidRunArtifactError(f"summary.json is missing {'/'.join(parts)}")
        current = current[part]
    return current


@dataclass(slots=True)
class PoolExhaustionTools:
    repository: FileRunRepository

    def get_pool_metrics(self, run_id: UUID) -> PoolExhaustionMetrics:
        run = self.repository.get(run_id)
        if run.manifest.scenario != RunScenario.CONNECTION_POOL_EXHAUSTION:
            raise InvalidRunArtifactError("Run is not a connection_pool_exhaustion scenario")
        summary = self.repository.read_json(run, "summary.json")
        facts = {
            "/before/concurrency": _path(summary, "before", "concurrency"),
            "/before/pool_size": _path(summary, "before", "pool_size"),
            "/after/pool_size": _path(summary, "after", "pool_size"),
            "/before/completed_requests": _path(summary, "before", "completed_requests"),
            "/after/completed_requests": _path(summary, "after", "completed_requests"),
            "/before/pool_timeouts": _path(summary, "before", "pool_timeouts"),
            "/after/pool_timeouts": _path(summary, "after", "pool_timeouts"),
            "/before/failure_rate_percent": _path(summary, "before", "failure_rate_percent"),
            "/after/failure_rate_percent": _path(summary, "after", "failure_rate_percent"),
            "/comparison/timeouts_removed": _path(summary, "comparison", "timeouts_removed"),
        }
        if int(facts["/before/pool_timeouts"]) <= 0 or int(facts["/after/pool_timeouts"]) != 0:
            raise InvalidRunArtifactError("Run does not prove before/after pool exhaustion")
        return PoolExhaustionMetrics(
            run_id=run_id,
            status=run.manifest.status,
            concurrency=int(facts["/before/concurrency"]),
            before_pool_size=int(facts["/before/pool_size"]),
            after_pool_size=int(facts["/after/pool_size"]),
            before_completed_requests=int(facts["/before/completed_requests"]),
            after_completed_requests=int(facts["/after/completed_requests"]),
            before_pool_timeouts=int(facts["/before/pool_timeouts"]),
            after_pool_timeouts=int(facts["/after/pool_timeouts"]),
            before_failure_rate_percent=float(facts["/before/failure_rate_percent"]),
            after_failure_rate_percent=float(facts["/after/failure_rate_percent"]),
            timeouts_removed=int(facts["/comparison/timeouts_removed"]),
            evidence=[_evidence(run, "summary.json", pointer, value) for pointer, value in facts.items()],
        )
