from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.ai.rag.chunking import chunk_markdown
from app.ai.rag.embeddings import EmbeddingProvider
from app.ai.rag.repository import PgVectorDocumentRepository
from app.ai.rag.schemas import RetrievedChunk
from app.ai.schemas import RunScenario


class DocumentRetriever(Protocol):
    async def search(self, question: str, scenario: RunScenario) -> list[RetrievedChunk]: ...


class RAGService:
    def __init__(self, repository: PgVectorDocumentRepository, embeddings: EmbeddingProvider, *, top_k: int = 5, threshold: float = 0.08):
        self.repository = repository
        self.embeddings = embeddings
        self.top_k = top_k
        self.threshold = threshold

    async def index_project(self, root: Path) -> dict[str, int]:
        candidates = [root / "README.md", *sorted((root / "docs").rglob("*.md"))]
        active: set[str] = set()
        changed = chunks_total = 0
        for path in candidates:
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            active.add(relative)
            chunks = chunk_markdown(path, path.read_text(encoding="utf-8"), source_path=relative)
            vectors = await self.embeddings.embed([item.content for item in chunks])
            count, did_change = await self.repository.synchronize_source(
                relative, chunks, vectors,
                embedding_model=self.embeddings.model,
                embedding_dimensions=self.embeddings.dimensions,
            )
            chunks_total += count
            changed += int(did_change)
        removed = await self.repository.remove_missing_sources(active)
        return {"documents": len(active), "changed": changed, "removed": removed, "chunks_written": chunks_total}

    async def search(self, question: str, scenario: RunScenario) -> list[RetrievedChunk]:
        vector = (await self.embeddings.embed([question]))[0]
        return await self.repository.search(
            vector, scenario=scenario, top_k=self.top_k, threshold=self.threshold
        )
