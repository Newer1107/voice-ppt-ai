"""HTTP client for the GPU unified service — transcription endpoint."""

import logging
import os
from typing import Optional

import httpx

from backend.src.config.settings import get_settings
from backend.src.core.ports.ai import TranscriptionPort, TranscriptionResult, TranscriptSegment
from backend.src.infrastructure.ai_client.base import BaseAIClient

logger = logging.getLogger(__name__)


class TranscriptionClient(BaseAIClient, TranscriptionPort):
    """Calls the unified GPU service's /ai/v1/transcribe endpoint."""

    def __init__(self):
        settings = get_settings()
        super().__init__(base_url=settings.AI_SERVICE_URL, api_key=settings.AI_API_KEY)

    async def transcribe(self, audio_path: str, language: Optional[str] = None, vad_filter: bool = True) -> TranscriptionResult:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        with open(audio_path, "rb") as f:
            files = {"audio_file": (os.path.basename(audio_path), f, "audio/wav")}
            params = {}
            if language: params["language"] = language
            params["vad_filter"] = str(vad_filter).lower()
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base_url}/ai/v1/transcribe", files=files, data=params)
                resp.raise_for_status()
                data = resp.json()
        segments = [TranscriptSegment(**s) for s in data.get("segments", [])]
        return TranscriptionResult(segments=segments, language=data.get("language", "en"), duration_seconds=data.get("duration_seconds", 0), processing_time_seconds=data.get("processing_time_seconds", 0))

    async def health(self) -> dict:
        try: return await self._get("/ai/v1/health")
        except Exception as e:
            logger.warning("Transcription health check failed: %s", e)
            return {"status": "unhealthy", "service": "transcription"}
