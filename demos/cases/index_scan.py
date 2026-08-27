"""PostgreSQL Seq Scan to Index Scan demonstration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(
    frozen=True,
    slots=True,
)
class IndexScanConfig:
    """Runtime parameters for the index-scan demonstration."""

    rows: int = 200_000
    target: int = 150_000
    runs: int = 5
    output_dir: Path = Path("demos/results")
    confirm_reset: bool = False

    def validate(self) -> None:
        """Validate the demonstration parameters."""

        if self.rows <= 0:
            raise ValueError(
                "rows must be greater than zero"
            )

        if not 1 <= self.target <= self.rows:
            raise ValueError(
                "target must be between 1 and rows"
            )

        if self.runs <= 0:
            raise ValueError(
                "runs must be greater than zero"
            )