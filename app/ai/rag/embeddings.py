"""Embedding providers; deterministic hashing keeps local demos reproducible."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

TOKEN = re.compile(r"[\w-]+", re.UNICODE)


class EmbeddingProvider(Protocol):
    model: str
    dimensions: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbeddingProvider:
    """Signed feature hashing: no download, stable and lexically meaningful."""

    def __init__(self, *, model: str = "taskgraph-hash-v1", dimensions: int = 768):
        self.model = model
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[slot] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

