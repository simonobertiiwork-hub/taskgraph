from pathlib import Path

import pytest

from app.ai.repositories.runs import FileRunRepository, InvalidRunArtifactError
from app.ai.tools.index_scan import IndexScanTools
from tests.unit.run_artifacts import write_index_run, write_race_run


def test_get_run_summary_returns_typed_measured_facts(tmp_path: Path):
    context = write_index_run(tmp_path)
    tools = IndexScanTools(FileRunRepository(tmp_path))

    result = tools.get_run_summary(context.run_id)

    assert result.dataset_rows == 200_000
    assert result.before_execution_time_ms == 13.0
    assert result.after_execution_time_ms == 0.07
    assert result.applied_index_name == "idx_tasks_title"
    assert len(result.evidence) == 8
    assert len({item.evidence_id for item in result.evidence}) == 8


def test_get_query_plan_reads_and_cross_checks_raw_explain(tmp_path: Path):
    context = write_index_run(tmp_path)
    tools = IndexScanTools(FileRunRepository(tmp_path))

    result = tools.get_query_plan(context.run_id)

    assert result.before.node_types == ["Seq Scan"]
    assert result.after.node_types == ["Index Scan"]
    assert result.after.index_names == ["idx_tasks_title"]
    assert result.transition_verified is True


def test_evidence_ids_are_stable_for_unchanged_artifacts(tmp_path: Path):
    context = write_index_run(tmp_path)
    tools = IndexScanTools(FileRunRepository(tmp_path))

    first = tools.get_run_summary(context.run_id)
    second = tools.get_run_summary(context.run_id)

    assert [item.evidence_id for item in first.evidence] == [
        item.evidence_id for item in second.evidence
    ]


def test_query_plan_rejects_summary_that_disagrees_with_raw_plan(tmp_path: Path):
    context = write_index_run(tmp_path, before_summary_nodes=["Index Scan"])
    tools = IndexScanTools(FileRunRepository(tmp_path))

    with pytest.raises(InvalidRunArtifactError, match="node types do not match"):
        tools.get_query_plan(context.run_id)


def test_index_tools_reject_non_index_run(tmp_path: Path):
    context = write_race_run(tmp_path)
    tools = IndexScanTools(FileRunRepository(tmp_path))

    with pytest.raises(InvalidRunArtifactError, match="not index_scan"):
        tools.get_run_summary(context.run_id)
