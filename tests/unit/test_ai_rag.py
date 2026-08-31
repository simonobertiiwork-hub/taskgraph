from pathlib import Path

import pytest

from app.ai.rag.chunking import chunk_markdown
from app.ai.rag.embeddings import HashEmbeddingProvider
from app.ai.schemas import RunScenario


def test_heading_chunker_preserves_metadata_and_overlap():
    text = "# Race Condition\n" + " ".join(f"token{i}" for i in range(900))
    chunks = chunk_markdown(
        Path("docs/cases/03-race-condition.md"), text,
        source_path="docs/cases/03-race-condition.md", max_tokens=500, overlap_tokens=80,
    )
    assert len(chunks) == 2
    assert chunks[0].scenario == RunScenario.RACE_CONDITION
    assert chunks[0].document_version == chunks[1].document_version
    assert chunks[0].content.split()[-80:] == chunks[1].content.split()[:80]


@pytest.mark.asyncio
async def test_hash_embeddings_are_deterministic_and_normalized():
    provider = HashEmbeddingProvider(dimensions=64)
    first, second = await provider.embed(["optimistic lock version", "optimistic lock version"])
    assert first == second
    assert sum(value * value for value in first) == pytest.approx(1.0)

