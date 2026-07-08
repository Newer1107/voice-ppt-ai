"""Stage 6: Generate narration scripts for each slide using Qwen.

Input: Slide content + aligned transcript segments
Output: Per-slide narration scripts
Verifies: Non-empty, matches slide, duration estimate reasonable
Communicates with GPU LLM service via HTTP.
"""

import logging
from typing import Optional

import httpx
from pydantic import BaseModel

from backend.src.config.settings import get_settings

logger = logging.getLogger(__name__)


class NarrationResult(BaseModel):
    slide_number: int
    script_text: str
    estimated_duration_seconds: int
    tone: str = "educational"
    key_points: list[str] = []


def generate_narrations(
    lecture_title: str,
    slides_with_transcripts: list[dict],
) -> list[NarrationResult]:
    """Generate narration scripts for all slides via the GPU LLM service.

    Each narration should:
    - Preserve technical accuracy
    - Improve clarity
    - Avoid repetition
    - Match the transcript
    - Respect speaker notes
    - Stay within reasonable duration (30-90s)
    """
    if not slides_with_transcripts:
        raise ValueError("No slides provided for narration generation")

    settings = get_settings()
    url = f"{settings.AI_SERVICE_URL}/ai/v1/generate-narration"

    payload = {
        "lecture_title": lecture_title,
        "slides": slides_with_transcripts,
    }

    try:
        resp = httpx.post(url, json=payload, timeout=1800)
        resp.raise_for_status()
        data = resp.json()
    except httpx.TimeoutException:
        logger.error("Narration generation timed out")
        raise
    except Exception as e:
        logger.exception("Narration generation failed")
        raise RuntimeError(f"Narration service error: {e}") from e

    narrations = []
    for n in data.get("narrations", []):
        # Verify output
        script = n.get("script_text", "")
        if not script or len(script.strip()) < 10:
            logger.warning("Slide %d narration too short, skipping", n.get("slide_number"))
            continue

        duration = n.get("estimated_duration_seconds", 30)
        if duration < 5 or duration > 300:
            logger.warning("Slide %d duration estimate out of range: %ds", n.get("slide_number"), duration)
            duration = max(30, min(duration, 120))

        narrations.append(NarrationResult(
            slide_number=n.get("slide_number", 0),
            script_text=script,
            estimated_duration_seconds=duration,
            tone=n.get("tone", "educational"),
            key_points=n.get("key_points", []),
        ))

    if not narrations:
        raise ValueError("No valid narrations generated")

    logger.info(
        "Generated %d narrations for '%s'",
        len(narrations), lecture_title,
    )

    return narrations
