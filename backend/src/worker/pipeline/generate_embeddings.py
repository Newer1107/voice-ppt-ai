"""Stage 4: Generate embeddings for slide text and transcript chunks.

Input: List of text strings
Output: List of embedding vectors
Verifies: Vector dimensions correct, no duplicate embeddings generated
Communicates with GPU embedding service via HTTP.
"""

import logging
import hashlib
from typing import Optional

import httpx
from pydantic import BaseModel

from backend.src.config.settings import get_settings

logger = logging.getLogger(__name__)

_EMBEDDING_CACHE: dict[str, list[float]] = {}


class EmbeddingBatchResult(BaseModel):
    """Result of embedding generation."""
    texts: list[str]
    vectors: list[list[float]]
    dimensions: int
    model: str = ""


def generate_embeddings(
    texts: list[str],
    use_cache: bool = True,
) -> EmbeddingBatchResult:
    """Generate embeddings for a list of text strings via the GPU service.

    Uses a simple in-memory cache keyed by SHA-256 hash to avoid
    generating duplicate embeddings for identical text.
    """
    if not texts:
        return EmbeddingBatchResult(texts=[], vectors=[], dimensions=0)

    settings = get_settings()
    url = f"{settings.AI_SERVICE_URL}/ai/v1/embed"

    # Deduplicate via cache
    results: list[Optional[list[float]]] = [None] * len(texts)
    uncached_indices = []
    uncached_texts = []

    for i, text in enumerate(texts):
        if use_cache:
            key = hashlib.sha256(text.encode()).hexdigest()
            if key in _EMBEDDING_CACHE:
                results[i] = _EMBEDDING_CACHE[key]
                continue
        uncached_indices.append(i)
        uncached_texts.append(text)

    # Call embedding service for uncached texts
    if uncached_texts:
        try:
            resp = httpx.post(
                url,
                json={"texts": uncached_texts, "normalize": True},
                timeout=600,
            )
            resp.raise_for_status()
            data = resp.json()
            for idx, vec in zip(uncached_indices, data["embeddings"]):
                vector = vec["vector"]
                results[idx] = vector
                if use_cache:
                    key = hashlib.sha256(texts[idx].encode()).hexdigest()
                    _EMBEDDING_CACHE[key] = vector
        except httpx.TimeoutException:
            logger.error("Embedding service timed out")
            raise
        except Exception as e:
            logger.exception("Embedding generation failed")
            raise RuntimeError(f"Embedding service error: {e}") from e

    # All results should now be populated
    vectors = [r for r in results if r is not None]
    dimensions = len(vectors[0]) if vectors else 0

    logger.info("Generated %d embeddings (d=%d, cache_hits=%d)", len(vectors), dimensions, len(texts) - len(uncached_texts))

    return EmbeddingBatchResult(
        texts=texts,
        vectors=vectors,
        dimensions=dimensions,
        model=data.get("model", "bge-m3") if uncached_texts else "bge-m3 (cached)",
    )
