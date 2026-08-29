"""Grounded tool for the reproducible Race Condition demonstration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.ai.repositories.runs import FileRunRepository, InvalidRunArtifactError
from app.ai.schemas import RaceConditionMetrics, RunScenario
from app.ai.tools.index_scan import _evidence


def _path(payload: dict[str, Any], *parts: str) -> Any:
    current: Any = payload
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            raise InvalidRunArtifactError(f"summary.json is missing {'/'.join(parts)}")
        current = current[part]
    return current


@dataclass(slots=True)
class RaceConditionTools:
    repository: FileRunRepository

    def get_concurrency_metrics(self, run_id: UUID) -> RaceConditionMetrics:
        run = self.repository.get(run_id)
        if run.manifest.scenario != RunScenario.RACE_CONDITION:
            raise InvalidRunArtifactError("Run is not a race_condition scenario")
        summary = self.repository.read_json(run, "summary.json")
        facts = {
            "/verification/last_write_wins/first_write_was_lost": _path(summary, "verification", "last_write_wins", "first_write_was_lost"),
            "/verification/last_write_wins/both_transactions_read_original": _path(summary, "verification", "last_write_wins", "both_transactions_read_original"),
            "/scenarios/pessimistic_lock/transaction_b/lock_wait_seconds": _path(summary, "scenarios", "pessimistic_lock", "transaction_b", "lock_wait_seconds"),
            "/scenarios/optimistic_lock/transaction_b_rows_updated": _path(summary, "scenarios", "optimistic_lock", "transaction_b_rows_updated"),
            "/scenarios/optimistic_lock/transaction_b_conflict_detected": _path(summary, "scenarios", "optimistic_lock", "transaction_b_conflict_detected"),
            "/scenarios/optimistic_lock/final/version": _path(summary, "scenarios", "optimistic_lock", "final", "version"),
        }
        if not facts["/verification/last_write_wins/first_write_was_lost"]:
            raise InvalidRunArtifactError("Run did not reproduce a lost update")
        return RaceConditionMetrics(
            run_id=run_id,
            status=run.manifest.status,
            lost_update_detected=bool(facts["/verification/last_write_wins/first_write_was_lost"]),
            both_transactions_read_original=bool(facts["/verification/last_write_wins/both_transactions_read_original"]),
            pessimistic_lock_wait_seconds=float(facts["/scenarios/pessimistic_lock/transaction_b/lock_wait_seconds"]),
            stale_writer_rows_updated=int(facts["/scenarios/optimistic_lock/transaction_b_rows_updated"]),
            optimistic_conflict_detected=bool(facts["/scenarios/optimistic_lock/transaction_b_conflict_detected"]),
            optimistic_final_version=int(facts["/scenarios/optimistic_lock/final/version"]),
            evidence=[_evidence(run, "summary.json", pointer, value) for pointer, value in facts.items()],
        )
