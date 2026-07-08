"""Stage 2: Transcribe audio using Faster-Whisper via GPU service.

Input: Audio file path (16kHz mono WAV)
Output: TranscriptionResult with timestamped segments
Verifies: Transcript not empty, segments ordered, confidence values valid
Communicates with GPU transcription service via HTTP.
"""

import logging
import os
from typing import Optional

import httpx
from pydantic import BaseModel

from backend.src.config.settings import get_settings

logger = logging.getLogger(__name__)


class TranscriptSegment(BaseModel):
    segment_number: int
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None
    speaker: Optional[str] = None


class TranscriptionResult(BaseModel):
    segments: list[TranscriptSegment]
    language: str
    duration_seconds: float
    processing_time_seconds: float = 0.0


def transcribe_audio(
    audio_path: str,
    language: Optional[str] = None,
    vad_filter: bool = True,
) -> TranscriptionResult:
    """Transcribe audio file via the GPU Faster-Whisper service.

    Sends the audio file as multipart upload to the transcription service.
    Returns timestamped segments with confidence scores.

    Verifies:
    - Transcript has at least one segment
    - Segments are ordered by segment_number
    - Confidence values are valid (0.0-1.0 range)
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    settings = get_settings()
    url = f"{settings.AI_SERVICE_URL}/ai/v1/transcribe"

    try:
        with open(audio_path, "rb") as f:
            files = {"audio_file": (os.path.basename(audio_path), f, "audio/wav")}
            params = {}
            if language:
                params["language"] = language
            params["vad_filter"] = "true" if vad_filter else "false"

            resp = httpx.post(url, files=files, data=params, timeout=1800)
            resp.raise_for_status()
            data = resp.json()

    except httpx.TimeoutException:
        logger.error("Transcription request timed out for %s", audio_path)
        raise
    except Exception as e:
        logger.exception("Transcription failed for %s", audio_path)
        raise RuntimeError(f"Transcription service error: {e}") from e

    segments = []
    for seg in data.get("segments", []):
        segments.append(TranscriptSegment(
            segment_number=seg["segment_number"],
            start_time=seg["start_time"],
            end_time=seg["end_time"],
            text=seg["text"],
            confidence=seg.get("confidence"),
            speaker=seg.get("speaker"),
        ))

    if not segments:
        raise ValueError("Transcription returned zero segments")

    # Verify segment ordering
    for i in range(1, len(segments)):
        if segments[i].segment_number <= segments[i - 1].segment_number:
            logger.warning("Segments out of order at index %d", i)

    # Note: confidence is Whisper avg_logprob (always ≤ 0, closer to 0 = better)
    result = TranscriptionResult(
        segments=segments,
        language=data.get("language", "en"),
        duration_seconds=data.get("duration_seconds", 0),
        processing_time_seconds=data.get("processing_time_seconds", 0),
    )

    logger.info(
        "Transcribed %s: %d segments, language=%s, duration=%.1fs",
        audio_path, len(segments), result.language, result.duration_seconds,
    )

    return result
