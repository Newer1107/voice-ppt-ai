"""HTTP client for the GPU unified service — TTS endpoints."""

import logging
from typing import Optional

import httpx

from backend.src.config.settings import get_settings
from backend.src.infrastructure.ai_client.base import BaseAIClient

logger = logging.getLogger(__name__)


class TTSClient(BaseAIClient):
    """Calls the unified GPU service's /ai/v1/tts and /ai/v1/clone-voice."""

    def __init__(self):
        settings = get_settings()
        super().__init__(base_url=settings.AI_SERVICE_URL, api_key=settings.AI_API_KEY)

    async def synthesize(self, text: str, voice_profile_id: Optional[str] = None, speed: float = 1.0) -> bytes:
        data = {"text": text, "speed": str(speed)}
        if voice_profile_id: data["voice_profile_id"] = voice_profile_id
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/ai/v1/tts", data=data)
            resp.raise_for_status()
            return resp.content

    async def clone_voice(self, audio_sample: bytes, name: str) -> str:
        files = {"audio_sample": ("sample.wav", audio_sample, "audio/wav"), "name": (None, name)}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/ai/v1/clone-voice", files=files)
            resp.raise_for_status()
            return resp.json().get("speaker_id", "")

    async def health(self) -> dict:
        try: return await self._get("/ai/v1/health")
        except Exception as e:
            logger.warning("TTS health check failed: %s", e)
            return {"status": "unhealthy", "service": "tts"}
