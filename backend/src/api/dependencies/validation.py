"""File upload validation utilities."""

import os
import unicodedata
from typing import Optional


ALLOWED_VIDEO_EXTENSIONS: set[str] = {".mp4", ".mov", ".mkv", ".webm"}
ALLOWED_AUDIO_EXTENSIONS: set[str] = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
ALLOWED_PPTX_EXTENSIONS: set[str] = {".pptx"}

# Magic bytes for MIME validation
MIME_SIGNATURES: dict[str, set[bytes]] = {
    "video": {
        b"\x00\x00\x00\x18ftypmp4",
        b"\x00\x00\x00\x20ftypisom",
        b"\x1a\x45\xdf\xa3",  # WebM
    },
    "audio": {
        b"ID3",  # MP3 ID3
        b"\xff\xfb",  # MP3
        b"\xff\xf3",  # MP3
        b"\xff\xf2",  # MP3
        b"RIFF",  # WAV
    },
    "pptx": {
        b"PK\x03\x04",  # ZIP-based (pptx, docx, xlsx)
    },
}


def validate_file_extension(filename: str, allowed_extensions: set[str]) -> bool:
    """Check if the file extension is in the allowed set."""
    _, ext = os.path.splitext(filename.lower())
    return ext in allowed_extensions


def validate_file_size(file_size: int, max_size: int) -> bool:
    """Check if file size is within limits."""
    return file_size <= max_size


def validate_mime_type(
    file_content: bytes, expected_category: str
) -> bool:
    """Validate MIME type by checking magic bytes."""
    signatures = MIME_SIGNATURES.get(expected_category, set())
    return any(file_content.startswith(sig) for sig in signatures)


def secure_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal."""
    # Normalize unicode
    filename = unicodedata.normalize("NFKD", filename)

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")

    # Limit length
    max_len = 255
    if len(filename) > max_len:
        name, ext = os.path.splitext(filename)
        filename = name[: max_len - len(ext)] + ext

    return filename


def validate_uploaded_file(
    filename: str,
    file_size: int,
    file_content: Optional[bytes] = None,
    allowed_extensions: set[str] | None = None,
    max_size: int | None = None,
    mime_category: str | None = None,
) -> tuple[bool, str]:
    """Run all file validations. Returns (is_valid, error_message)."""
    if not filename:
        return False, "Filename is required"

    if allowed_extensions and not validate_file_extension(filename, allowed_extensions):
        return False, f"Unsupported file type: {filename}"

    if max_size is not None and not validate_file_size(file_size, max_size):
        return False, f"File too large (max {max_size / (1024*1024):.0f}MB)"

    if mime_category and file_content and not validate_mime_type(file_content, mime_category):
        return False, "File content does not match expected type"

    return True, ""
