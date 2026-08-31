"""Grounded tools for the PostgreSQL index-scan demonstration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.ai.repositories.runs import (
    FileRunRepository,
    InvalidRunArtifactError,
    StoredRun,
)
from app.ai.schemas import (
    EvidenceRef,
    IndexScanPhase,
    IndexScanPlanComparison,
    IndexScanRunSummary,
    JsonValue,
    RunScenario,
)

INDEX_NODE_TYPES = {"Index Scan", "Index Only Scan", "Bitmap Index Scan"}


def _required(mapping: dict[str, Any], key: str, artifact: str) -> Any:
    try:
        return mapping[key]
    except KeyError as exc:
        raise InvalidRunArtifactError(
            f"Artifact {artifact!r} is missing field {key!r}"
        ) from exc


def _evidence(
    run: StoredRun,
    artifact_name: str,
    json_pointer: str,
    value: JsonValue,
) -> EvidenceRef:
    descriptor = run.manifest.artifacts[artifact_name]
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    material = (
        f"{run.manifest.run_id}|{artifact_name}|{descriptor.sha256}|"
        f"{json_pointer}|{canonical}"
    )
    evidence_id = "ev_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    return EvidenceRef(
        evidence_id=evidence_id,
        run_id=run.manifest.run_id,
        artifact_name=artifact_name,
        artifact_sha256=descriptor.sha256,
        json_pointer=json_pointer,
        value=value,
    )


def _walk_plan_nodes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [plan]
    for child in plan.get("Plans", []):
        if not isinstance(child, dict):
            raise InvalidRunArtifactError("EXPLAIN Plans must contain objects")
        nodes.extend(_walk_plan_nodes(child))
    return nodes


def _normalize_plan_artifact(payload: Any, artifact_name: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or not payload:
        raise InvalidRunArtifactError(
            f"Artifact {artifact_name!r} must contain measured plans"
        )
    explains: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("explain"), dict):
            raise InvalidRunArtifactError(
                f"Artifact {artifact_name!r} contains an invalid plan entry"
            )
        explain = item["explain"]
        if not isinstance(explain.get("Plan"), dict):
            raise InvalidRunArtifactError(
                f"Artifact {artifact_name!r} contains no EXPLAIN Plan"
            )
        explains.append(explain)
    return explains


def _plan_features(explains: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    nodes = [node for explain in explains for node in _walk_plan_nodes(explain["Plan"])]
    node_types = sorted(
        {str(node["Node Type"]) for node in nodes if "Node Type" in node}
    )
    index_names = sorted(
        {str(node["Index Name"]) for node in nodes if "Index Name" in node}
    )
    return node_types, index_names


@dataclass(frozen=True, slots=True)
class IndexScanTools:
    """Safe tool facade whose public methods accept only a run id."""

    repository: FileRunRepository

    def _load(self, run_id: UUID) -> tuple[StoredRun, dict[str, Any], dict[str, Any]]:
        run = self.repository.get(run_id)
        if run.manifest.scenario != RunScenario.INDEX_SCAN:
            raise InvalidRunArtifactError(
                f"Run {run_id} is {run.manifest.scenario.value}, not index_scan"
            )
        metadata = self.repository.read_json(run, "metadata.json")
        summary = self.repository.read_json(run, "summary.json")
        if not isinstance(metadata, dict) or not isinstance(summary, dict):
            raise InvalidRunArtifactError(
                "Index-scan metadata and summary must be objects"
            )
        if metadata.get("case") != RunScenario.INDEX_SCAN.value:
            raise InvalidRunArtifactError("metadata.json has an unexpected case")
        return run, metadata, summary

    def get_run_summary(self, run_id: UUID) -> IndexScanRunSummary:
        """Return measured before/after facts with stable evidence references."""
        run, metadata, summary = self._load(run_id)
        try:
            dataset = _required(metadata, "dataset", "metadata.json")
            index = _required(metadata, "index", "metadata.json")
            before = _required(summary, "before", "summary.json")
            after = _required(summary, "after", "summary.json")
            comparison = _required(summary, "comparison", "summary.json")
            rows = int(_required(dataset, "rows", "metadata.json"))
            lookup_title = str(_required(dataset, "lookup_title", "metadata.json"))
            query = str(_required(metadata, "query", "metadata.json"))
            before_ms = float(
                _required(before, "median_execution_time_ms", "summary.json")
            )
            after_ms = float(
                _required(after, "median_execution_time_ms", "summary.json")
            )
            speedup_raw = comparison.get("speedup")
            reduction_raw = comparison.get("execution_time_reduction_percent")
            speedup = float(speedup_raw) if speedup_raw is not None else None
            reduction = float(reduction_raw) if reduction_raw is not None else None
            index_name = str(_required(index, "name", "metadata.json"))
        except (TypeError, ValueError) as exc:
            raise InvalidRunArtifactError(
                "Index-scan summary contains an invalid value type"
            ) from exc

        evidence = [
            _evidence(run, "metadata.json", "/dataset/rows", rows),
            _evidence(run, "metadata.json", "/dataset/lookup_title", lookup_title),
            _evidence(run, "metadata.json", "/query", query),
            _evidence(
                run,
                "summary.json",
                "/before/median_execution_time_ms",
                before_ms,
            ),
            _evidence(
                run,
                "summary.json",
                "/after/median_execution_time_ms",
                after_ms,
            ),
            _evidence(run, "summary.json", "/comparison/speedup", speedup),
            _evidence(
                run,
                "summary.json",
                "/comparison/execution_time_reduction_percent",
                reduction,
            ),
            _evidence(run, "metadata.json", "/index/name", index_name),
        ]
        return IndexScanRunSummary(
            run_id=run_id,
            status=run.manifest.status,
            dataset_rows=rows,
            lookup_title=lookup_title,
            query=query,
            before_execution_time_ms=before_ms,
            after_execution_time_ms=after_ms,
            speedup=speedup,
            execution_time_reduction_percent=reduction,
            applied_index_name=index_name,
            evidence=evidence,
        )

    def get_query_plan(self, run_id: UUID) -> IndexScanPlanComparison:
        """Return verified plan features from the raw PostgreSQL artifacts."""
        run, metadata, summary = self._load(run_id)
        before_raw = self.repository.read_json(run, "before.json")
        after_raw = self.repository.read_json(run, "after.json")
        before_explains = _normalize_plan_artifact(before_raw, "before.json")
        after_explains = _normalize_plan_artifact(after_raw, "after.json")
        before_nodes, before_indexes = _plan_features(before_explains)
        after_nodes, after_indexes = _plan_features(after_explains)

        try:
            before_summary = _required(summary, "before", "summary.json")
            after_summary = _required(summary, "after", "summary.json")
            verification = _required(summary, "verification", "summary.json")
            index = _required(metadata, "index", "metadata.json")
            query = str(_required(metadata, "query", "metadata.json"))
            index_name = str(_required(index, "name", "metadata.json"))
            index_definition = str(_required(index, "definition", "metadata.json"))
            before_ms = float(
                _required(
                    before_summary,
                    "median_execution_time_ms",
                    "summary.json",
                )
            )
            after_ms = float(
                _required(
                    after_summary,
                    "median_execution_time_ms",
                    "summary.json",
                )
            )
            before_runs = int(_required(before_summary, "runs", "summary.json"))
            after_runs = int(_required(after_summary, "runs", "summary.json"))
        except (TypeError, ValueError) as exc:
            raise InvalidRunArtifactError(
                "Index-scan plan summary contains an invalid value type"
            ) from exc

        if before_runs != len(before_explains) or after_runs != len(after_explains):
            raise InvalidRunArtifactError(
                "Raw EXPLAIN run count does not match summary.json"
            )
        if before_nodes != sorted(before_summary.get("node_types", [])):
            raise InvalidRunArtifactError(
                "before.json node types do not match summary.json"
            )
        if after_nodes != sorted(after_summary.get("node_types", [])):
            raise InvalidRunArtifactError(
                "after.json node types do not match summary.json"
            )
        if before_indexes != sorted(before_summary.get("index_names", [])):
            raise InvalidRunArtifactError(
                "before.json index names do not match summary.json"
            )
        if after_indexes != sorted(after_summary.get("index_names", [])):
            raise InvalidRunArtifactError(
                "after.json index names do not match summary.json"
            )

        transition_verified = bool(
            verification.get("before_uses_seq_scan")
            and verification.get("after_uses_index_plan")
            and verification.get("after_uses_expected_index")
            and "Seq Scan" in before_nodes
            and any(node in INDEX_NODE_TYPES for node in after_nodes)
            and index_name in after_indexes
        )
        before = IndexScanPhase(
            measured_runs=before_runs,
            median_execution_time_ms=before_ms,
            node_types=before_nodes,
            index_names=before_indexes,
        )
        after = IndexScanPhase(
            measured_runs=after_runs,
            median_execution_time_ms=after_ms,
            node_types=after_nodes,
            index_names=after_indexes,
        )
        evidence = [
            _evidence(run, "metadata.json", "/query", query),
            _evidence(run, "metadata.json", "/index/name", index_name),
            _evidence(
                run,
                "metadata.json",
                "/index/definition",
                index_definition,
            ),
            _evidence(run, "summary.json", "/before/node_types", before_nodes),
            _evidence(
                run,
                "summary.json",
                "/before/index_names",
                before_indexes,
            ),
            _evidence(run, "summary.json", "/after/node_types", after_nodes),
            _evidence(run, "summary.json", "/after/index_names", after_indexes),
        ]
        return IndexScanPlanComparison(
            run_id=run_id,
            query=query,
            index_name=index_name,
            index_definition=index_definition,
            before=before,
            after=after,
            transition_verified=transition_verified,
            evidence=evidence,
        )
