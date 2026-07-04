"""HTTP client for the GPU unified service — embedding endpoint."""

import logging
from typing import Optional

import httpx

from backend.src.config.settings import get_settings
from backend.src.infrastructure.ai_client.base import BaseAIClient

logger = logging.getLogger(__name__)


class EmbeddingClient(BaseAIClient):
    """Calls the unified GPU service's /ai/v1/embed endpoint."""

    def __init__(self):
        settings = get_settings()
        super().__init__(base_url=settings.AI_SERVICE_URL, api_key=settings.AI_API_KEY)

    async def embed_text(self, texts: list[str], normalize: bool = True) -> dict:
        if not texts:
            return {"embeddings": [], "model": "bge-m3"}
        return await self._post("/ai/v1/embed", json_data={"texts": texts, "normalize": normalize})

    async def embed_dimensions(self) -> int:
        try:
            data = await self._get("/ai/v1/dimensions")
            return data.get("dimensions", 1024)
        except Exception:
            return 1024

    async def health(self) -> dict:
        try: return await self._get("/ai/v1/health")
        except Exception as e:
            logger.warning("Embedding health check failed: %s", e)
            return {"status": "unhealthy", "service": "embedding"}
