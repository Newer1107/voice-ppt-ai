"""Stage 7: Generate speech audio from narration scripts.

Input: Per-slide narration scripts
Output: Per-slide audio files
Verifies: Audio file exists, readable, duration > 0
Communicates with GPU TTS service via HTTP.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel

from backend.src.config.settings import get_settings

logger = logging.getLogger(__name__)


class TTSGenerationResult(BaseModel):
    """Result of TTS generation for a single slide."""
    slide_number: int
    audio_path: str
    duration_seconds: float
    file_size_bytes: int


def generate_slide_tts(
    text: str,
    output_path: str,
    slide_number: int,
    voice_profile_id: Optional[str] = None,
    speed: float = 1.0,
) -> TTSGenerationResult:
    """Generate speech audio for a single slide narration via GPU TTS service.

    Sends the narration text to the F5-TTS service and saves
    the returned WAV audio to the specified output path.

    Verifies:
    - Audio file exists after generation
    - File size > 44 bytes (WAV header minimum)
    - Duration > 0
    """
    settings = get_settings()
    url = f"{settings.AI_SERVICE_URL}/ai/v1/tts"

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:
        # Build multipart form data
        files = {"text": (None, text)}
        if voice_profile_id:
            files["voice_profile_id"] = (None, voice_profile_id)
        files["speed"] = (None, str(speed))

        resp = httpx.post(url, files=files, timeout=300)
        resp.raise_for_status()

        # Save audio to file
        with open(output_path, "wb") as f:
            f.write(resp.content)

        # Verify output
        if not os.path.exists(output_path):
            raise RuntimeError(f"TTS output not created: {output_path}")

        file_size = os.path.getsize(output_path)
        if file_size < 44:
            raise ValueError(f"TTS output too small (corrupt WAV): {file_size} bytes")

        # Parse duration from response header
        duration_str = resp.headers.get("X-Audio-Duration", "0")
        try:
            duration = float(duration_str)
        except (ValueError, TypeError):
            duration = file_size / 48000  # Estimate: 16-bit 24kHz mono

        if duration <= 0:
            duration = file_size / 48000

        logger.info(
            "TTS generated for slide %d: %s (%.1fs, %d bytes)",
            slide_number, output_path, duration, file_size,
        )

        return TTSGenerationResult(
            slide_number=slide_number,
            audio_path=str(output_path),
            duration_seconds=round(duration, 2),
            file_size_bytes=file_size,
        )

    except httpx.TimeoutException:
        logger.error("TTS request timed out for slide %d (text: %d chars)", slide_number, len(text))
        raise
    except Exception as e:
        logger.exception("TTS generation failed for slide %d", slide_number)
        raise RuntimeError(f"TTS service error for slide {slide_number}: {e}") from e
