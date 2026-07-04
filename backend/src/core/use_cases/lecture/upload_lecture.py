"""Upload lecture use case — handles file upload and pipeline kickoff."""

import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import (
    BadRequestError,
    NotFoundError,
    UnsupportedFileTypeError,
    FileTooLargeError,
)
from backend.src.core.dto.lecture import UploadLectureResponse
from backend.src.core.ports.storage import StoragePort
from backend.src.infrastructure.db.models.lecture import LectureModel
from backend.src.infrastructure.db.models.file_record import FileModel
from backend.src.infrastructure.db.models.job import JobModel
from backend.src.infrastructure.db.repositories.project_repo import ProjectRepository
from backend.src.infrastructure.db.repositories.lecture_repo import LectureRepository
from backend.src.infrastructure.storage.local_storage import StoragePaths
from backend.src.config.settings import get_settings

logger = logging.getLogger(__name__)

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
ALLOWED_PPTX_EXTENSIONS = {".pptx"}

VIDEO_MIME_PREFIXES = {b"\x00\x00\x00\x18ftypmp4", b"\x00\x00\x00\x20ftypisom", b"\x00\x00\x00\x1cftyp"}
AUDIO_MIME_PREFIXES = {b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}
PPTX_MIME_PREFIX = b"PK\x03\x04"


def _validate_extension(filename: str, allowed: set[str]) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return f".{ext}" in allowed


def _validate_mime(content: bytes, allowed_prefixes: set[bytes]) -> bool:
    return any(content.startswith(p) for p in allowed_prefixes)


class UploadLectureUseCase:
    """Handle lecture upload with file validation and storage."""

    def __init__(self, session: AsyncSession, storage: StoragePort):
        self._session = session
        self._storage = storage
        self._project_repo = ProjectRepository(session)
        self._lecture_repo = LectureRepository(session)
        self._settings = get_settings()

    async def execute(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        title: str,
        video_data: Optional[tuple[str, bytes]] = None,  # (filename, content)
        audio_data: Optional[tuple[str, bytes]] = None,
        pptx_data: Optional[tuple[str, bytes]] = None,
        voice_profile_id: Optional[uuid.UUID] = None,
    ) -> UploadLectureResponse:
        # Validate project exists and belongs to user
        project = await self._project_repo.find_by_user_and_id(user_id, project_id)
        if not project:
            raise NotFoundError(message="Project not found")

        # Check at least one media file provided
        if not video_data and not audio_data:
            raise BadRequestError(
                message="At least one video or audio file is required"
            )

        # Determine input type
        input_type = "video" if video_data else "audio"

        # Validate and store video
        video_path = None
        if video_data:
            filename, content = video_data
            if not _validate_extension(filename, ALLOWED_VIDEO_EXTENSIONS):
                raise UnsupportedFileTypeError(
                    message=f"Unsupported video format: {filename}",
                )
            if len(content) > self._settings.MAX_VIDEO_SIZE_BYTES:
                raise FileTooLargeError(message="Video file exceeds maximum size (2GB)")
            video_path = str(
                StoragePaths.lecture_source_video("new", str(project_id))
            )
            video_path = await self._storage.store(
                video_path.replace("new", "{lecture_id}"), content
            )

        # Validate and store audio
        audio_path = None
        if audio_data:
            filename, content = audio_data
            if not _validate_extension(filename, ALLOWED_AUDIO_EXTENSIONS):
                raise UnsupportedFileTypeError(
                    message=f"Unsupported audio format: {filename}",
                )
            if len(content) > self._settings.MAX_AUDIO_SIZE_BYTES:
                raise FileTooLargeError(message="Audio file exceeds maximum size (500MB)")
            audio_path = str(
                StoragePaths.lecture_source_audio("new", str(project_id))
            )
            audio_path = await self._storage.store(
                audio_path.replace("new", "{lecture_id}"), content
            )

        # Validate and store PPTX
        pptx_path = None
        if pptx_data:
            filename, content = pptx_data
            if not _validate_extension(filename, ALLOWED_PPTX_EXTENSIONS):
                raise UnsupportedFileTypeError(
                    message=f"Unsupported file format: {filename}",
                )
            if len(content) > self._settings.MAX_PPTX_SIZE_BYTES:
                raise FileTooLargeError(message="PPTX file exceeds maximum size (200MB)")
            pptx_path = str(
                StoragePaths.lecture_pptx("new", str(project_id))
            )
            pptx_path = await self._storage.store(
                pptx_path.replace("new", "{lecture_id}"), content
            )

        # Create lecture record
        lecture = LectureModel(
            project_id=project_id,
            title=title,
            input_type=input_type,
            status="pending",
            video_path=video_path,
            audio_path=audio_path,
            pptx_path=pptx_path,
            voice_profile_id=voice_profile_id,
        )
        lecture = await self._lecture_repo.add(lecture)

        # Create initial pipeline job
        job = JobModel(
            lecture_id=lecture.id,
            job_type="full_pipeline",
            status="pending",
            payload={
                "extract_audio": audio_path is None,
                "has_pptx": pptx_path is not None,
            },
        )
        job = await self._lecture_repo.add(job)  # using existing session

        # Create file records for tracking
        file_records_data = []
        if video_data:
            file_records_data.append((video_data[1], video_path, "video_source", video_data[0]))
        if audio_data:
            file_records_data.append((audio_data[1], audio_path, "audio_source", audio_data[0]))
        if pptx_data:
            file_records_data.append((pptx_data[1], pptx_path, "pptx_source", pptx_data[0]))

        for content_bytes, path, file_type, original_name in file_records_data:
            if content_bytes and path:
                checksum = hashlib.sha256(content_bytes).hexdigest()
                file_record = FileModel(
                    user_id=user_id,
                    lecture_id=lecture.id,
                    file_type=file_type,
                    original_name=original_name,
                    storage_path=path,
                    file_size_bytes=len(content_bytes),
                    checksum_sha256=checksum,
                )
                self._session.add(file_record)

        await self._session.flush()

        logger.info(
            "Lecture uploaded: id=%s project=%s type=%s",
            lecture.id, project_id, input_type,
        )

        return UploadLectureResponse(
            id=lecture.id,
            title=lecture.title,
            input_type=input_type,
            status=lecture.status,
            job_id=job.id,
            created_at=lecture.created_at,
        )
