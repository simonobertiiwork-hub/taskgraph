"""Deterministic Markdown chunking with heading-aware boundaries."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.ai.rag.schemas import DocumentChunk
from app.ai.schemas import RunScenario

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TOKEN = re.compile(r"\S+")


def infer_scenario(path: Path, text: str) -> RunScenario | None:
    haystack = f"{path.as_posix()}\n{text[:2000]}".lower()
    if any(word in haystack for word in ("race-condition", "race_condition", "lost update", "optimistic lock")):
        return RunScenario.RACE_CONDITION
    if any(word in haystack for word in ("index-scan", "index_scan", "seq scan", "explain analyze")):
        return RunScenario.INDEX_SCAN
    if any(word in haystack for word in ("connection-pool", "pool exhaustion", "connection pool")):
        return RunScenario.CONNECTION_POOL_EXHAUSTION
    return None


def _windows(words: list[str], *, size: int, overlap: int) -> list[str]:
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        chunks.append(" ".join(words[start : start + size]))
        if start + size >= len(words):
            break
        start += size - overlap
    return chunks


def chunk_markdown(
    path: Path,
    text: str,
    *,
    source_path: str | None = None,
    max_tokens: int = 550,
    overlap_tokens: int = 80,
) -> list[DocumentChunk]:
    if max_tokens <= overlap_tokens or overlap_tokens < 0:
        raise ValueError("chunk size must be greater than overlap")
    version = hashlib.sha256(text.encode("utf-8")).hexdigest()
    scenario = infer_scenario(path, text)
    sections: list[tuple[str, list[str]]] = []
    title = path.stem
    body: list[str] = []
    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            if body:
                sections.append((title, body))
            title, body = match.group(2).strip(), []
        else:
            body.append(line)
    if body:
        sections.append((title, body))

    result: list[DocumentChunk] = []
    index = 0
    for section, lines in sections:
        words = TOKEN.findall("\n".join(lines).strip())
        for content in _windows(words, size=max_tokens, overlap=overlap_tokens):
            result.append(
                DocumentChunk(
                    source_path=source_path or path.as_posix(),
                    section=section,
                    scenario=scenario,
                    chunk_index=index,
                    content=content,
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    document_version=version,
                )
            )
            index += 1
    return result

