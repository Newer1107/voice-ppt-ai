"""Lecture routes — upload, detail, status."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies.auth import get_current_user
from backend.src.api.dependencies.providers import get_storage
from backend.src.core.dto.lecture import (
    UploadLectureResponse,
    LectureDetailResponse,
    LectureStatusResponse,
)
from backend.src.core.ports.storage import StoragePort
from backend.src.core.use_cases.lecture.upload_lecture import UploadLectureUseCase
from backend.src.core.use_cases.lecture.get_lecture import GetLectureUseCase
from backend.src.core.use_cases.lecture.get_lecture_status import (
    GetLectureStatusUseCase,
)
from backend.src.infrastructure.db.models.user import UserModel
from backend.src.infrastructure.db.session import get_db

router = APIRouter(
    prefix="/api/v1/lectures",
    tags=["Lectures"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/upload", response_model=UploadLectureResponse, status_code=202)
async def upload_lecture(
    project_id: uuid.UUID = Form(...),
    title: str = Form(...),
    video_file: Optional[UploadFile] = File(None),
    audio_file: Optional[UploadFile] = File(None),
    pptx_file: Optional[UploadFile] = File(None),
    voice_profile_id: Optional[uuid.UUID] = Form(None),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StoragePort = Depends(get_storage),
):
    """Upload a lecture with video/audio and optional PPTX.

    At least one of video_file or audio_file is required.
    Returns 202 with lecture_id and job_id for async processing.
    """
    # Read file contents
    video_data = None
    if video_file and video_file.filename:
        content = await video_file.read()
        video_data = (video_file.filename, content)

    audio_data = None
    if audio_file and audio_file.filename:
        content = await audio_file.read()
        audio_data = (audio_file.filename, content)

    pptx_data = None
    if pptx_file and pptx_file.filename:
        content = await pptx_file.read()
        pptx_data = (pptx_file.filename, content)

    use_case = UploadLectureUseCase(session, storage)
    return await use_case.execute(
        user_id=current_user.id,
        project_id=project_id,
        title=title,
        video_data=video_data,
        audio_data=audio_data,
        pptx_data=pptx_data,
        voice_profile_id=voice_profile_id,
    )


@router.get("/{lecture_id}", response_model=LectureDetailResponse)
async def get_lecture(
    lecture_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get lecture details with slides and narrations."""
    use_case = GetLectureUseCase(session)
    return await use_case.execute(
        user_id=current_user.id,
        lecture_id=lecture_id,
    )


@router.get("/{lecture_id}/status", response_model=LectureStatusResponse)
async def get_lecture_status(
    lecture_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get lecture processing status and job progress."""
    use_case = GetLectureStatusUseCase(session)
    return await use_case.execute(
        user_id=current_user.id,
        lecture_id=lecture_id,
    )
