"""Strict schemas shared by demo artifacts and future LLM tools."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

RUN_SCHEMA_VERSION = 1


class StrictModel(BaseModel):
    """Reject undeclared fields so artifact format drift is visible."""

    model_config = ConfigDict(extra="forbid")


class RunScenario(StrEnum):
    """Demonstration scenarios accepted by the AI evidence layer."""

    INDEX_SCAN = "index_scan"
    RACE_CONDITION = "race_condition"
    CONNECTION_POOL_EXHAUSTION = "connection_pool_exhaustion"


class RunStatus(StrEnum):
    """Terminal state of a reproducible demonstration run."""

    PASSED = "passed"
    FAILED = "failed"


class ArtifactDescriptor(StrictModel):
    """Integrity metadata for one file owned by a run."""

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1)


class RunManifest(StrictModel):
    """Stable, versioned entry point for all evidence in one run."""

    schema_version: Literal[RUN_SCHEMA_VERSION] = RUN_SCHEMA_VERSION
    run_id: UUID
    scenario: RunScenario
    started_at_utc: datetime
    completed_at_utc: datetime
    status: RunStatus
    artifacts: dict[str, ArtifactDescriptor]


class EvidenceRef(StrictModel):
    """Trace one normalized fact back to an immutable run artifact."""

    evidence_id: str = Field(pattern=r"^ev_[0-9a-f]{20}$")
    run_id: UUID
    source_type: Literal["artifact"] = "artifact"
    artifact_name: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    json_pointer: str = Field(pattern=r"^/")
    value: JsonValue


class IndexScanPhase(StrictModel):
    """Normalized metrics and plan features for one measurement phase."""

    measured_runs: int = Field(gt=0)
    median_execution_time_ms: float = Field(ge=0)
    node_types: list[str]
    index_names: list[str]


class IndexScanRunSummary(StrictModel):
    """Compact output of the get_run_summary read-only tool."""

    schema_version: Literal[RUN_SCHEMA_VERSION] = RUN_SCHEMA_VERSION
    run_id: UUID
    scenario: Literal[RunScenario.INDEX_SCAN] = RunScenario.INDEX_SCAN
    status: RunStatus
    dataset_rows: int = Field(gt=0)
    lookup_title: str = Field(min_length=1)
    query: str = Field(min_length=1)
    before_execution_time_ms: float = Field(ge=0)
    after_execution_time_ms: float = Field(ge=0)
    speedup: float | None = Field(default=None, gt=0)
    execution_time_reduction_percent: float | None = None
    applied_index_name: str = Field(min_length=1)
    evidence: list[EvidenceRef]


class IndexScanPlanComparison(StrictModel):
    """Compact output of the get_query_plan read-only tool."""

    schema_version: Literal[RUN_SCHEMA_VERSION] = RUN_SCHEMA_VERSION
    run_id: UUID
    scenario: Literal[RunScenario.INDEX_SCAN] = RunScenario.INDEX_SCAN
    query: str = Field(min_length=1)
    index_name: str = Field(min_length=1)
    index_definition: str = Field(min_length=1)
    before: IndexScanPhase
    after: IndexScanPhase
    transition_verified: bool
    evidence: list[EvidenceRef]
