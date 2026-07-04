"""File download routes."""

import uuid
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies.auth import get_current_user
from backend.src.api.dependencies.providers import get_storage
from backend.src.api.errors.handlers import NotFoundError, ForbiddenError
from backend.src.core.ports.storage import StoragePort
from backend.src.infrastructure.db.models.user import UserModel
from backend.src.infrastructure.db.repositories.file_repo import FileRepository
from backend.src.infrastructure.db.repositories.lecture_repo import LectureRepository
from backend.src.infrastructure.db.repositories.project_repo import ProjectRepository
from backend.src.infrastructure.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/files",
    tags=["Files"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/{file_id}")
async def download_file(
    file_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StoragePort = Depends(get_storage),
):
    """Download a file by its ID.

    Verifies that the current user owns the file (or the file's
    associated lecture belongs to one of the user's projects).
    """
    file_repo = FileRepository(session)
    file_record = await file_repo.get(file_id)

    if not file_record:
        raise NotFoundError(message="File not found")

    # Check ownership
    if file_record.user_id != current_user.id:
        # Check if the file's lecture belongs to one of user's projects
        if file_record.lecture_id:
            lecture_repo = LectureRepository(session)
            lecture = await lecture_repo.get(file_record.lecture_id)
            if lecture:
                project_repo = ProjectRepository(session)
                project = await project_repo.find_by_user_and_id(
                    current_user.id, lecture.project_id
                )
                if not project:
                    raise ForbiddenError(message="Not authorized to access this file")
        else:
            raise ForbiddenError(message="Not authorized to access this file")

    # Retrieve file content
    try:
        content = await storage.retrieve(file_record.storage_path)
    except FileNotFoundError:
        raise NotFoundError(message="File content not found on storage")

    # Determine media type
    media_type = file_record.mime_type or "application/octet-stream"
    filename = file_record.original_name

    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
        },
    )
