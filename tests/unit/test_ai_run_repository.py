import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.ai.repositories.runs import (
    ArtifactIntegrityError,
    FileRunRepository,
    InvalidRunArtifactError,
    RunNotFoundError,
)
from app.ai.schemas import RunScenario
from tests.unit.run_artifacts import write_index_run, write_race_run


def test_repository_loads_run_and_integrity_checked_json(tmp_path: Path):
    context = write_index_run(tmp_path)
    repository = FileRunRepository(tmp_path)

    run = repository.get(context.run_id)
    summary = repository.read_json(run, "summary.json")

    assert run.manifest.run_id == context.run_id
    assert summary["before"]["median_execution_time_ms"] == 13.0


def test_repository_returns_latest_run_for_scenario(tmp_path: Path):
    write_race_run(tmp_path)
    expected = write_index_run(tmp_path)
    repository = FileRunRepository(tmp_path)

    run = repository.latest(RunScenario.INDEX_SCAN)

    assert run.manifest.run_id == expected.run_id


def test_repository_reports_missing_run(tmp_path: Path):
    repository = FileRunRepository(tmp_path)

    with pytest.raises(RunNotFoundError, match="was not found"):
        repository.get(uuid4())


def test_repository_detects_artifact_tampering(tmp_path: Path):
    context = write_index_run(tmp_path)
    repository = FileRunRepository(tmp_path)
    run = repository.get(context.run_id)
    summary_path = context.result_dir / "summary.json"
    summary_path.write_text('{"status":"changed"}\n', encoding="utf-8")

    with pytest.raises(ArtifactIntegrityError, match="does not match manifest"):
        repository.read_json(run, "summary.json")


def test_repository_rejects_artifact_path_traversal(tmp_path: Path):
    context = write_index_run(tmp_path)
    manifest_path = context.result_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["summary.json"]["path"] = "../summary.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    repository = FileRunRepository(tmp_path)
    run = repository.get(context.run_id)

    with pytest.raises(InvalidRunArtifactError, match="escapes"):
        repository.artifact_path(run, "summary.json")
