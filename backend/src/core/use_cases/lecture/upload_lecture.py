"""Upload lecture use case — handles file upload and pipeline kickoff."""

import uuid
import hashlib
import logging
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


def _validate_extension(filename: str, allowed: set[str]) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return f".{ext}" in allowed


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
        video_data: Optional[tuple[str, bytes]] = None,
        audio_data: Optional[tuple[str, bytes]] = None,
        pptx_data: Optional[tuple[str, bytes]] = None,
        voice_profile_id: Optional[uuid.UUID] = None,
    ) -> UploadLectureResponse:
        project = await self._project_repo.find_by_user_and_id(user_id, project_id)
        if not project:
            raise NotFoundError(message="Project not found")

        if not video_data and not audio_data:
            raise BadRequestError(message="At least one video or audio file is required")

        input_type = "video" if video_data else "audio"

        # Generate lecture ID upfront so we can use it in file paths
        lecture_id = uuid.uuid4()
        lid = str(lecture_id)
        pid = str(project_id)

        video_path = audio_path = pptx_path = None

        if video_data:
            filename, content = video_data
            if not _validate_extension(filename, ALLOWED_VIDEO_EXTENSIONS):
                raise UnsupportedFileTypeError(message=f"Unsupported video format: {filename}")
            if len(content) > self._settings.MAX_VIDEO_SIZE_BYTES:
                raise FileTooLargeError(message="Video file exceeds maximum size (2GB)")
            path = str(StoragePaths.lecture_source_video(lid, pid))
            video_path = await self._storage.store(path, content)

        if audio_data:
            filename, content = audio_data
            if not _validate_extension(filename, ALLOWED_AUDIO_EXTENSIONS):
                raise UnsupportedFileTypeError(message=f"Unsupported audio format: {filename}")
            if len(content) > self._settings.MAX_AUDIO_SIZE_BYTES:
                raise FileTooLargeError(message="Audio file exceeds maximum size (500MB)")
            path = str(StoragePaths.lecture_source_audio(lid, pid))
            audio_path = await self._storage.store(path, content)

        if pptx_data:
            filename, content = pptx_data
            if not _validate_extension(filename, ALLOWED_PPTX_EXTENSIONS):
                raise UnsupportedFileTypeError(message=f"Unsupported file format: {filename}")
            if len(content) > self._settings.MAX_PPTX_SIZE_BYTES:
                raise FileTooLargeError(message="PPTX file exceeds maximum size (200MB)")
            path = str(StoragePaths.lecture_pptx(lid, pid))
            pptx_path = await self._storage.store(path, content)

        lecture = LectureModel(
            id=lecture_id,
            project_id=project_id, title=title, input_type=input_type, status="pending",
            video_path=video_path, audio_path=audio_path, pptx_path=pptx_path,
            voice_profile_id=voice_profile_id,
        )
        lecture = await self._lecture_repo.add(lecture)

        job = JobModel(
            lecture_id=lecture.id, job_type="full_pipeline", status="pending",
            payload={"extract_audio": audio_path is None, "has_pptx": pptx_path is not None},
        )
        job = await self._lecture_repo.add(job)

        # Create file records
        file_specs = []
        if video_data:
            file_specs.append((video_data[1], video_path, "video_source", video_data[0]))
        if audio_data:
            file_specs.append((audio_data[1], audio_path, "audio_source", audio_data[0]))
        if pptx_data:
            file_specs.append((pptx_data[1], pptx_path, "pptx_source", pptx_data[0]))

        for content_bytes, path, ftype, original_name in file_specs:
            if content_bytes and path:
                self._session.add(FileModel(
                    user_id=user_id, lecture_id=lecture.id, file_type=ftype,
                    original_name=original_name, storage_path=path,
                    file_size_bytes=len(content_bytes),
                    checksum_sha256=hashlib.sha256(content_bytes).hexdigest(),
                ))

        await self._session.flush()

        # Dispatch Celery task after flush (commit happens in get_db after handler returns).
        # countdown=3 gives the async session time to commit before the worker picks it up.
        try:
            from backend.src.worker.tasks.lecture_tasks import process_lecture_pipeline
            process_lecture_pipeline.apply_async(args=[lid], countdown=3)
            logger.info("Dispatched pipeline task for lecture %s", lecture.id)
        except ImportError:
            logger.warning("Celery task not available — pipeline will not run automatically")

        logger.info("Lecture uploaded: id=%s project=%s type=%s", lecture.id, project_id, input_type)

        return UploadLectureResponse(
            id=lecture.id, title=lecture.title, input_type=input_type,
            status=lecture.status, job_id=job.id, created_at=lecture.created_at,
        )
