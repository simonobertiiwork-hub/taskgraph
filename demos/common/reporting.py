"""Result-file helpers shared by TaskGraph demonstrations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def create_result_directory(base_dir: Path, case_name: str) -> Path:
    """Create a unique UTC-stamped directory for one demo run."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    result_dir = base_dir.expanduser().resolve() / case_name / timestamp
    result_dir.mkdir(parents=True, exist_ok=False)
    return result_dir


def write_json(path: Path, payload: Any) -> None:
    """Write stable, human-readable JSON with a trailing newline."""
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, content: str) -> None:
    """Write UTF-8 text with exactly one trailing newline."""
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
