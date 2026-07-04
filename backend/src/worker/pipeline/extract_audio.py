"""Stage 1: Extract audio from video using FFmpeg.

Input: Video file path
Output: 16kHz mono WAV file path + duration
Verifies: File exists, duration > 0, sample rate correct
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AudioExtractionResult(BaseModel):
    """Result of audio extraction."""
    audio_path: str
    duration_seconds: float
    sample_rate: int = 16000
    channels: int = 1


def extract_audio(
    video_path: str,
    output_path: Optional[str] = None,
) -> AudioExtractionResult:
    """Extract audio from video file as 16kHz mono WAV using FFmpeg.

    Applies loudnorm filter for volume normalization.
    Raises FileNotFoundError if input missing, ValueError if no audio track.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Probe for audio streams
    probe_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0", video_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
    if "audio" not in result.stdout:
        raise ValueError(f"No audio stream found in video: {video_path}")

    # Determine output path
    if output_path is None:
        base = Path(video_path).stem
        output_path = os.path.join(os.path.dirname(video_path), f"{base}_extracted.wav")

    # Extract audio with volume normalization
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-af", "loudnorm=I=-16:LRA=11:TP=-1.5",
        str(output_path),
    ]

    logger.info("Extracting audio: %s -> %s", video_path, output_path)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr}")

    if not os.path.exists(output_path):
        raise RuntimeError(f"Output file not created: {output_path}")

    # Verify output with ffprobe
    duration = _get_media_duration(output_path)
    if duration <= 0:
        raise ValueError(f"Extracted audio has zero duration: {output_path}")

    file_size = os.path.getsize(output_path)
    logger.info(
        "Audio extracted: %s (duration=%.1fs, size=%d bytes)",
        output_path, duration, file_size,
    )

    return AudioExtractionResult(
        audio_path=str(output_path),
        duration_seconds=duration,
        sample_rate=16000,
        channels=1,
    )


def _get_media_duration(file_path: str) -> float:
    """Get media file duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0", file_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return float(result.stdout.strip())
    except (ValueError, TypeError):
        return 0.0
