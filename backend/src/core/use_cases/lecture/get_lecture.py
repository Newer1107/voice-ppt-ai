"""Get lecture detail use case."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import NotFoundError
from backend.src.core.dto.lecture import (
    LectureDetailResponse,
    NarrationSummaryResponse,
    SlideNarrationResponse,
)
from backend.src.infrastructure.db.models.file_record import FileModel
from backend.src.infrastructure.db.repositories.lecture_repo import LectureRepository
from backend.src.infrastructure.db.repositories.narration_repo import (
    NarrationRepository,
)
from backend.src.infrastructure.db.repositories.slide_repo import SlideRepository


class GetLectureUseCase:
    """Handle lecture detail retrieval with slides and narrations."""

    def __init__(self, session: AsyncSession):
        self._lecture_repo = LectureRepository(session)
        self._slide_repo = SlideRepository(session)
        self._narration_repo = NarrationRepository(session)

    async def execute(
        self,
        user_id: uuid.UUID,
        lecture_id: uuid.UUID,
    ) -> LectureDetailResponse:
        # Find lecture via project ownership
        # We need to fetch the lecture and verify project ownership
        lecture = await self._lecture_repo.get(lecture_id)
        if not lecture:
            raise NotFoundError(message="Lecture not found")

        # Verify project ownership
        from backend.src.infrastructure.db.repositories.project_repo import (
            ProjectRepository,
        )
        project_repo = ProjectRepository(self._lecture_repo._session)
        project = await project_repo.find_by_user_and_id(
            user_id, lecture.project_id
        )
        if not project:
            raise NotFoundError(message="Lecture not found")

        # Query FileModel records for download URLs
        stmt = select(FileModel).where(FileModel.lecture_id == lecture_id)
        result = await self._lecture_repo._session.execute(stmt)
        file_models = result.scalars().all()

        # Build lookup: original_name -> FileModel (for narration audio)
        audio_file_map = {
            fm.original_name: fm
            for fm in file_models
            if fm.file_type == "narration_audio"
        }

        # Find narrated PPTX file
        pptx_file = next((fm for fm in file_models if fm.file_type == "narrated_pptx"), None)
        narrated_pptx_url = f"/api/v1/files/{pptx_file.id}" if pptx_file else None

        # Get slides with narrations
        slides = await self._slide_repo.list_by_lecture(lecture_id)
        slide_responses = []
        for slide in slides:
            narration = None
            if slide.narration:
                original_name = f"slide_{slide.slide_number:03d}.wav"
                audio_file = audio_file_map.get(original_name)
                narration = NarrationSummaryResponse(
                    id=slide.narration.id,
                    script_text=slide.narration.script_text,
                    audio_url=(
                        f"/api/v1/files/{audio_file.id}"
                        if audio_file
                        else None
                    ),
                    duration_seconds=slide.narration.duration_seconds,
                    status=slide.narration.status,
                )
            slide_responses.append(
                SlideNarrationResponse(
                    id=slide.id,
                    slide_number=slide.slide_number,
                    raw_text=slide.raw_text,
                    narration=narration,
                )
            )

        return LectureDetailResponse(
            id=lecture.id,
            project_id=lecture.project_id,
            title=lecture.title,
            input_type=lecture.input_type,
            status=lecture.status,
            duration_seconds=lecture.duration_seconds,
            slides=slide_responses,
            transcript_url=None,
            narrated_pptx_url=narrated_pptx_url,
            created_at=lecture.created_at,
            updated_at=lecture.updated_at,
        )
