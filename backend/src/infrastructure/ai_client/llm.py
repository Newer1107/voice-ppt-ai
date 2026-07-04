"""HTTP client for the GPU unified service — LLM endpoints."""

import logging
from typing import Optional

import httpx

from backend.src.config.settings import get_settings
from backend.src.infrastructure.ai_client.base import BaseAIClient

logger = logging.getLogger(__name__)


class LLMClient(BaseAIClient):
    """Calls the unified GPU service's /ai/v1/align and /ai/v1/generate-narration."""

    def __init__(self):
        settings = get_settings()
        super().__init__(base_url=settings.AI_SERVICE_URL, api_key=settings.AI_API_KEY)

    async def align_transcript(self, transcript: dict, slides: list[dict], candidates: Optional[list[dict]] = None) -> dict:
        payload = {"transcript": transcript, "slides": slides}
        if candidates: payload["candidates"] = candidates
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/ai/v1/align", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def generate_narration(self, lecture_title: str, slides: list[dict]) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/ai/v1/generate-narration", json={"lecture_title": lecture_title, "slides": slides})
            resp.raise_for_status()
            return resp.json()

    async def health(self) -> dict:
        try: return await self._get("/ai/v1/health")
        except Exception as e:
            logger.warning("LLM health check failed: %s", e)
            return {"status": "unhealthy", "service": "llm"}
