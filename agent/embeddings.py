"""Voyage AI embeddings wrapper."""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache

import voyageai

EMBED_DIMS = 1024


@lru_cache(maxsize=1)
def _client() -> voyageai.Client | None:
    key = os.environ.get("VOYAGE_API_KEY")
    return voyageai.Client(api_key=key) if key else None


def embed(text: str) -> list[float]:
    c = _client()
    if c is None:
        return _dummy(text)
    result = c.embed(
        [text],
        model=os.environ.get("VOYAGE_MODEL", "voyage-3-large"),
        input_type="query",
    )
    return result.embeddings[0]


def _dummy(text: str) -> list[float]:
    h = hashlib.sha256(text.encode()).digest()
    seed = [b / 255.0 - 0.5 for b in h]
    return (seed * (EMBED_DIMS // len(seed) + 1))[:EMBED_DIMS]
