"""Async pgvector persistence and cosine retrieval."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.ai.rag.schemas import DocumentChunk, RetrievedChunk
from app.ai.schemas import RunScenario
from app.models.ai_document import AIDocumentChunk


class PgVectorDocumentRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]):
        self.sessions = sessions

    async def synchronize_source(
        self,
        source_path: str,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        *,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> tuple[int, bool]:
        async with self.sessions() as session:
            existing = (
                await session.execute(
                    select(AIDocumentChunk).where(AIDocumentChunk.source_path == source_path)
                    .order_by(AIDocumentChunk.chunk_index)
                )
            ).scalars().all()
            signature = [(item.chunk_index, item.content_hash, item.embedding_model) for item in existing]
            wanted = [(item.chunk_index, item.content_hash, embedding_model) for item in chunks]
            if signature == wanted:
                return 0, False
            await session.execute(
                delete(AIDocumentChunk).where(AIDocumentChunk.source_path == source_path)
            )
            for chunk, vector in zip(chunks, vectors, strict=True):
                session.add(
                    AIDocumentChunk(
                        source_path=chunk.source_path,
                        section=chunk.section,
                        scenario=chunk.scenario.value if chunk.scenario else None,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        content_hash=chunk.content_hash,
                        document_version=chunk.document_version,
                        embedding_model=embedding_model,
                        embedding_dimensions=embedding_dimensions,
                        embedding=vector,
                    )
                )
            await session.commit()
            return len(chunks), True

    async def remove_missing_sources(self, active_sources: set[str]) -> int:
        async with self.sessions() as session:
            stored = set((await session.execute(select(AIDocumentChunk.source_path))).scalars())
            missing = stored - active_sources
            if missing:
                await session.execute(delete(AIDocumentChunk).where(AIDocumentChunk.source_path.in_(missing)))
                await session.commit()
            return len(missing)

    async def search(
        self,
        vector: list[float],
        *,
        scenario: RunScenario | None,
        top_k: int,
        threshold: float,
    ) -> list[RetrievedChunk]:
        distance = AIDocumentChunk.embedding.cosine_distance(vector)
        statement = select(AIDocumentChunk, distance.label("distance"))
        if scenario is not None:
            statement = statement.where(
                (AIDocumentChunk.scenario == scenario.value) | (AIDocumentChunk.scenario.is_(None))
            )
        rows = (await self._execute(statement.order_by(distance).limit(top_k))).all()
        result: list[RetrievedChunk] = []
        for item, raw_distance in rows:
            score = max(0.0, min(1.0, 1.0 - float(raw_distance)))
            if score < threshold:
                continue
            result.append(
                RetrievedChunk(
                    chunk_id=item.id,
                    source_path=item.source_path,
                    section=item.section,
                    scenario=RunScenario(item.scenario) if item.scenario else None,
                    content=item.content,
                    score=score,
                )
            )
        return result

    async def _execute(self, statement):
        async with self.sessions() as session:
            return await session.execute(statement)
