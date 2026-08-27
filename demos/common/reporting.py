"""Result-file helpers shared by TaskGraph demonstrations."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.ai.schemas import (
    RUN_SCHEMA_VERSION,
    ArtifactDescriptor,
    RunManifest,
    RunScenario,
    RunStatus,
)


@dataclass(frozen=True, slots=True)
class DemoRunContext:
    """Identity and filesystem location allocated before a demo starts."""

    run_id: UUID
    scenario: RunScenario
    started_at_utc: datetime
    result_dir: Path


def create_run_context(base_dir: Path, case_name: str) -> DemoRunContext:
    """Create one unique, versioned run directory and stable UUID."""
    try:
        scenario = RunScenario(case_name)
    except ValueError as exc:
        raise ValueError(f"Unsupported demo scenario: {case_name}") from exc

    started_at = datetime.now(timezone.utc)
    run_id = uuid4()
    timestamp = started_at.strftime("%Y%m%dT%H%M%S%fZ")
    result_dir = (
        base_dir.expanduser().resolve() / scenario.value / f"{timestamp}_{run_id}"
    )
    result_dir.mkdir(parents=True, exist_ok=False)
    return DemoRunContext(
        run_id=run_id,
        scenario=scenario,
        started_at_utc=started_at,
        result_dir=result_dir,
    )


def create_result_directory(base_dir: Path, case_name: str) -> Path:
    """Create a result directory for compatibility with older callers."""
    return create_run_context(base_dir, case_name).result_dir


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finalize_run(
    context: DemoRunContext,
    *,
    status: str,
    artifact_names: Iterable[str],
) -> Path:
    """Write manifest.json after every declared artifact is complete."""
    try:
        run_status = RunStatus(status)
    except ValueError as exc:
        raise ValueError(f"Unsupported run status: {status}") from exc

    descriptors: dict[str, ArtifactDescriptor] = {}
    for artifact_name in artifact_names:
        candidate = (context.result_dir / artifact_name).resolve()
        try:
            relative = candidate.relative_to(context.result_dir)
        except ValueError as exc:
            raise ValueError(
                f"Artifact escapes run directory: {artifact_name}"
            ) from exc
        if not candidate.is_file():
            raise FileNotFoundError(f"Run artifact does not exist: {candidate}")
        media_type = mimetypes.guess_type(candidate.name)[0] or (
            "application/octet-stream"
        )
        descriptors[artifact_name] = ArtifactDescriptor(
            path=relative.as_posix(),
            sha256=_file_sha256(candidate),
            size_bytes=candidate.stat().st_size,
            media_type=media_type,
        )

    manifest = RunManifest(
        schema_version=RUN_SCHEMA_VERSION,
        run_id=context.run_id,
        scenario=context.scenario,
        started_at_utc=context.started_at_utc,
        completed_at_utc=datetime.now(timezone.utc),
        status=run_status,
        artifacts=descriptors,
    )
    manifest_path = context.result_dir / "manifest.json"
    write_json(manifest_path, manifest.model_dump(mode="json"))
    return manifest_path


def write_json(path: Path, payload: Any) -> None:
    """Write stable, human-readable JSON with a trailing newline."""
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, content: str) -> None:
    """Write UTF-8 text with exactly one trailing newline."""
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
