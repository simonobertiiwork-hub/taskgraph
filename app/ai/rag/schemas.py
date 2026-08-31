from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.ai.schemas import RunScenario


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    source_path: str
    section: str
    scenario: RunScenario | None
    chunk_index: int
    content: str
    content_hash: str
    document_version: str


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: UUID
    source_path: str
    section: str
    scenario: RunScenario | None
    content: str
    score: float

    def citation_payload(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "source_path": self.source_path,
            "section": self.section,
            "scenario": self.scenario,
            "score": round(self.score, 6),
        }

