"""Strict schemas shared by demo artifacts and future LLM tools."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

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


class LLMUsage(StrictModel):
    """Token counts reported by an OpenAI-compatible provider."""

    model_config = ConfigDict(extra="ignore")

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class IncidentAnalysisStatus(StrEnum):
    """Terminal state of one AI analysis request."""

    COMPLETED = "completed"
    FAILED = "failed"


class IncidentAnalysisRequest(StrictModel):
    """Validated user request; question text is always treated as data."""

    run_id: UUID
    question: str = Field(min_length=5, max_length=1_000)


class SupportedStatement(StrictModel):
    """One technical statement with explicit evidence references."""

    text: str = Field(min_length=1, max_length=1_500)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def reject_duplicate_evidence(self) -> SupportedStatement:
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence_ids must not contain duplicates")
        return self


class IndexScanMeasuredResult(StrictModel):
    """Numeric result copied from get_run_summary rather than calculated by LLM."""

    statement: SupportedStatement
    before_ms: float = Field(ge=0)
    after_ms: float = Field(ge=0)
    speedup: float = Field(gt=0)


class IncidentReportDraft(StrictModel):
    """Strict structured output produced and then deterministically validated."""

    run_id: UUID
    scenario: Literal[RunScenario.INDEX_SCAN] = RunScenario.INDEX_SCAN
    summary: SupportedStatement
    problem: SupportedStatement
    root_cause: SupportedStatement
    applied_fix: SupportedStatement
    result: IndexScanMeasuredResult
    limitations: list[str] = Field(default_factory=list, max_length=5)


class RequestedToolCall(StrictModel):
    """Normalized function call selected by the language model."""

    call_id: str = Field(min_length=1, max_length=200)
    tool_name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, JsonValue]


class ExecutedToolCall(StrictModel):
    """One allowlisted tool invocation and its structured output."""

    call_id: str = Field(min_length=1, max_length=200)
    tool_name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, JsonValue]
    result: dict[str, JsonValue]
    latency_ms: float = Field(ge=0)


class ProviderCallRecord(StrictModel):
    """Operational metadata for one model call."""

    purpose: Literal["tool_planning", "report", "repair"]
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    attempts: int = Field(ge=1)
    latency_ms: float = Field(ge=0)
    provider_request_id: str | None = None
    usage: LLMUsage | None = None


class IncidentAnalysisResponse(StrictModel):
    """Completed graph result with tools, provider metadata, and validation."""

    analysis_id: UUID
    request: IncidentAnalysisRequest
    status: IncidentAnalysisStatus
    report: IncidentReportDraft | None = None
    tool_calls: list[ExecutedToolCall]
    provider_calls: list[ProviderCallRecord]
    validation_errors: list[str]
    latency_ms: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_terminal_state(self) -> IncidentAnalysisResponse:
        if self.status == IncidentAnalysisStatus.COMPLETED:
            if self.report is None or self.validation_errors:
                raise ValueError("Completed analysis requires a validated report")
        elif self.report is not None:
            raise ValueError("Failed analysis must not expose an unvalidated report")
        return self
