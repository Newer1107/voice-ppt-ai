"""Local filesystem storage implementation."""

import os
import aiofiles
import logging
from pathlib import Path

from backend.src.core.ports.storage import StoragePort

logger = logging.getLogger(__name__)


class LocalStorage(StoragePort):
    """Store files on the local filesystem.

    All paths are resolved relative to a root directory.
    Path traversal attacks are prevented by resolving to absolute
    paths and verifying they stay within the root.
    """

    def __init__(self, root_path: str = "./storage"):
        self._root = Path(root_path).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorage root: %s", self._root)

    def _resolve(self, storage_path: str) -> Path:
        """Resolve a storage path to an absolute path, guarding against traversal."""
        # Clean the path
        clean = storage_path.lstrip("/").replace("\\", "/")
        resolved = (self._root / clean).resolve()

        # Guard against path traversal
        if self._root not in resolved.parents and resolved != self._root:
            raise PermissionError(f"Path traversal detected: {storage_path}")

        return resolved

    async def store(self, file_path: str, content: bytes) -> str:
        """Store content at the given path relative to root."""
        abs_path = self._resolve(file_path)
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(str(abs_path), "wb") as f:
            await f.write(content)

        # Return the relative storage path
        rel_path = str(abs_path.relative_to(self._root)).replace("\\", "/")
        logger.debug("Stored file: %s (%d bytes)", rel_path, len(content))
        return rel_path

    async def retrieve(self, storage_path: str) -> bytes:
        """Retrieve content from the given storage path."""
        abs_path = self._resolve(storage_path)
        if not abs_path.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")

        async with aiofiles.open(str(abs_path), "rb") as f:
            return await f.read()

    async def delete(self, storage_path: str) -> None:
        """Delete file at the given storage path."""
        abs_path = self._resolve(storage_path)
        if abs_path.exists():
            abs_path.unlink()
            logger.debug("Deleted file: %s", storage_path)

    async def exists(self, storage_path: str) -> bool:
        """Check if file exists at the given storage path."""
        abs_path = self._resolve(storage_path)
        return abs_path.exists()

    async def get_size(self, storage_path: str) -> int:
        """Get file size in bytes."""
        abs_path = self._resolve(storage_path)
        if not abs_path.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")
        return abs_path.stat().st_size


class StoragePaths:
    """Helper to generate consistent storage paths."""

    STORAGE_ROOT = Path("/data/storage")

    @classmethod
    def lecture_source_video(cls, lecture_id: str, project_id: str) -> Path:
        return (
            cls.STORAGE_ROOT
            / "projects"
            / project_id
            / "lectures"
            / lecture_id
            / "source"
            / "video.mp4"
        )

    @classmethod
    def lecture_source_audio(cls, lecture_id: str, project_id: str) -> Path:
        return (
            cls.STORAGE_ROOT
            / "projects"
            / project_id
            / "lectures"
            / lecture_id
            / "source"
            / "audio.mp3"
        )

    @classmethod
    def lecture_pptx(cls, lecture_id: str, project_id: str) -> Path:
        return (
            cls.STORAGE_ROOT
            / "projects"
            / project_id
            / "lectures"
            / lecture_id
            / "source"
            / "slides.pptx"
        )

    @classmethod
    def extracted_audio(cls, lecture_id: str, project_id: str) -> Path:
        return (
            cls.STORAGE_ROOT
            / "projects"
            / project_id
            / "lectures"
            / lecture_id
            / "audio"
            / "extracted.wav"
        )

    @classmethod
    def narration_audio(
        cls, lecture_id: str, project_id: str, slide_number: int
    ) -> Path:
        return (
            cls.STORAGE_ROOT
            / "projects"
            / project_id
            / "lectures"
            / lecture_id
            / "audio_narrations"
            / f"slide_{slide_number:03d}.wav"
        )

    @classmethod
    def output_pptx(cls, lecture_id: str, project_id: str) -> Path:
        return (
            cls.STORAGE_ROOT
            / "projects"
            / project_id
            / "lectures"
            / lecture_id
            / "output"
            / "narrated_lecture.pptx"
        )

    @classmethod
    def voice_sample(cls, user_id: str, profile_id: str) -> Path:
        return (
            cls.STORAGE_ROOT
            / "users"
            / user_id
            / "voice_samples"
            / profile_id
            / "sample.wav"
        )

    @classmethod
    def temp_upload(cls, session_id: str) -> Path:
        return cls.STORAGE_ROOT / "temp" / "uploads" / session_id
