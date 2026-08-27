import json
from pathlib import Path

import pytest

from app.ai.schemas import RunManifest
from demos.common.reporting import create_run_context, finalize_run, write_text


def test_create_run_context_allocates_uuid_and_scenario_directory(tmp_path: Path):
    context = create_run_context(tmp_path, "index_scan")

    assert context.result_dir.is_dir()
    assert context.result_dir.parent.name == "index_scan"
    assert str(context.run_id) in context.result_dir.name


def test_finalize_run_writes_versioned_manifest_with_digest(tmp_path: Path):
    context = create_run_context(tmp_path, "index_scan")
    write_text(context.result_dir / "summary.json", '{"status":"passed"}')

    manifest_path = finalize_run(
        context,
        status="passed",
        artifact_names=("summary.json",),
    )
    manifest = RunManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )

    assert manifest.run_id == context.run_id
    assert manifest.schema_version == 1
    assert manifest.artifacts["summary.json"].size_bytes > 0
    assert len(manifest.artifacts["summary.json"].sha256) == 64
    assert json.loads((context.result_dir / "summary.json").read_text())["status"] == (
        "passed"
    )


def test_finalize_run_refuses_missing_artifact(tmp_path: Path):
    context = create_run_context(tmp_path, "index_scan")

    with pytest.raises(FileNotFoundError, match="does not exist"):
        finalize_run(
            context,
            status="passed",
            artifact_names=("missing.json",),
        )


def test_create_run_context_rejects_unknown_scenario(tmp_path: Path):
    with pytest.raises(ValueError, match="Unsupported demo scenario"):
        create_run_context(tmp_path, "unknown")
