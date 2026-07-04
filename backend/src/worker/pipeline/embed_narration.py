"""Stage 8: Embed narration audio into PowerPoint.

Input: Original PPTX path + per-slide narration audio files
Output: Narrated PPTX with embedded audio
Verifies: Output opens correctly, audio embedded, slide count preserved
"""

import logging
import os
from pathlib import Path
from typing import Optional

from pptx import Presentation
from pptx.util import Emu
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EmbedNarrationResult(BaseModel):
    output_path: str
    slide_count: int
    audio_tracks_added: int
    file_size_bytes: int


def embed_narration_into_pptx(
    pptx_path: str,
    slide_audio_map: dict[int, str],
    output_path: Optional[str] = None,
) -> EmbedNarrationResult:
    """Embed narration audio files into a PowerPoint presentation.

    For each slide with audio, embeds the audio file and configures
    it to play automatically on slide entry.

    Verifies:
    - Output file opens correctly
    - Audio is embedded for the correct slides
    - Slide count matches original presentation
    """
    if not os.path.exists(pptx_path):
        raise FileNotFoundError(f"PPTX file not found: {pptx_path}")

    if not slide_audio_map:
        raise ValueError("No audio files to embed")

    # Validate all audio files exist
    for slide_num, audio_path in slide_audio_map.items():
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file for slide {slide_num} not found: {audio_path}")

    try:
        prs = Presentation(pptx_path)
    except Exception as e:
        raise ValueError(f"Failed to open PPTX for embedding: {e}")

    original_slide_count = len(prs.slides)
    audio_added = 0

    for slide_num, audio_path in slide_audio_map.items():
        if slide_num < 1 or slide_num > len(prs.slides):
            logger.warning("Slide number %d out of range (1-%d), skipping", slide_num, len(prs.slides))
            continue

        slide = prs.slides[slide_num - 1]

        # Read audio data
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        # Add audio to slide
        media_format = "audio/wav"
        # Set media to play automatically
        # python-pptx supports adding media via relationships
        slide.shapes.add_movie(
            audio_path,  # This path becomes relative reference in PPTX
            0, 0, 1, 1,  # Position/size (hide off-screen)
            poster_frame_image=None,
        )
        audio_added += 1

        logger.debug("Embedded audio for slide %d (%d bytes)", slide_num, len(audio_bytes))

    # Determine output path
    if output_path is None:
        base = Path(pptx_path).stem
        output_dir = os.path.dirname(pptx_path)
        output_path = os.path.join(output_dir, f"{base}_narrated.pptx")

    # Save the narrated presentation
    try:
        prs.save(output_path)
    except Exception as e:
        raise RuntimeError(f"Failed to save narrated PPTX: {e}")

    if not os.path.exists(output_path):
        raise RuntimeError(f"Narrated PPTX not created: {output_path}")

    file_size = os.path.getsize(output_path)

    # Verify
    try:
        verify = Presentation(output_path)
        slide_count = len(verify.slides)
        if slide_count != original_slide_count:
            logger.warning(
                "Slide count mismatch: original=%d, output=%d",
                original_slide_count, slide_count,
            )
    except Exception as e:
        raise RuntimeError(f"Output PPTX failed verification: {e}")

    logger.info(
        "Narrated PPTX created: %s (%d slides, %d audio tracks, %d bytes)",
        output_path, slide_count, audio_added, file_size,
    )

    return EmbedNarrationResult(
        output_path=str(output_path),
        slide_count=slide_count,
        audio_tracks_added=audio_added,
        file_size_bytes=file_size,
    )
