"""Read and integrity-check versioned TaskGraph demonstration runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.ai.schemas import RunManifest, RunScenario


class RunRepositoryError(RuntimeError):
    """Base class for controlled run-repository failures."""


class RunNotFoundError(RunRepositoryError):
    """Raised when a requested run does not exist."""


class InvalidRunArtifactError(RunRepositoryError):
    """Raised when a manifest or JSON artifact violates its contract."""


class ArtifactIntegrityError(RunRepositoryError):
    """Raised when an artifact no longer matches its recorded digest."""


@dataclass(frozen=True, slots=True)
class StoredRun:
    """A validated manifest and the directory that owns its artifacts."""

    manifest: RunManifest
    directory: Path


def file_sha256(path: Path) -> str:
    """Return a streaming SHA-256 digest without loading a file at once."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FileRunRepository:
    """Locate runs below a controlled root and verify every file read."""

    def __init__(self, results_root: Path):
        self.results_root = results_root.expanduser().resolve()

    def _manifest_paths(self) -> list[Path]:
        if not self.results_root.exists():
            return []
        return sorted(self.results_root.rglob("manifest.json"))

    def _load_manifest(self, path: Path) -> StoredRun:
        try:
            manifest = RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValidationError, ValueError) as exc:
            raise InvalidRunArtifactError(f"Invalid run manifest: {path}") from exc
        return StoredRun(manifest=manifest, directory=path.parent.resolve())

    def get(self, run_id: UUID) -> StoredRun:
        """Return exactly one run with the requested identifier."""
        matches = [
            run
            for path in self._manifest_paths()
            if (run := self._load_manifest(path)).manifest.run_id == run_id
        ]
        if not matches:
            raise RunNotFoundError(f"Run {run_id} was not found")
        if len(matches) > 1:
            raise InvalidRunArtifactError(
                f"Run id {run_id} is duplicated below {self.results_root}"
            )
        return matches[0]

    def latest(self, scenario: RunScenario) -> StoredRun:
        """Return the most recently completed run for one scenario."""
        matches = [
            run
            for path in self._manifest_paths()
            if (run := self._load_manifest(path)).manifest.scenario == scenario
        ]
        if not matches:
            raise RunNotFoundError(
                f"No {scenario.value} runs were found below {self.results_root}"
            )
        return max(matches, key=lambda run: run.manifest.completed_at_utc)

    def artifact_path(self, run: StoredRun, artifact_name: str) -> Path:
        """Resolve an allowlisted artifact and reject path traversal."""
        descriptor = run.manifest.artifacts.get(artifact_name)
        if descriptor is None:
            raise InvalidRunArtifactError(
                f"Run {run.manifest.run_id} has no artifact {artifact_name!r}"
            )

        candidate = (run.directory / descriptor.path).resolve()
        try:
            candidate.relative_to(run.directory)
        except ValueError as exc:
            raise InvalidRunArtifactError(
                f"Artifact {artifact_name!r} escapes its run directory"
            ) from exc

        if not candidate.is_file():
            raise InvalidRunArtifactError(
                f"Artifact {artifact_name!r} does not exist: {candidate}"
            )
        if candidate.stat().st_size != descriptor.size_bytes:
            raise ArtifactIntegrityError(
                f"Artifact {artifact_name!r} size does not match manifest"
            )
        if file_sha256(candidate) != descriptor.sha256:
            raise ArtifactIntegrityError(
                f"Artifact {artifact_name!r} checksum does not match manifest"
            )
        return candidate

    def read_json(self, run: StoredRun, artifact_name: str) -> Any:
        """Read an integrity-checked JSON artifact."""
        path = self.artifact_path(run, artifact_name)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise InvalidRunArtifactError(
                f"Artifact {artifact_name!r} is not valid UTF-8 JSON"
            ) from exc
