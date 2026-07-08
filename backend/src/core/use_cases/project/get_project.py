"""Get project use case."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import NotFoundError
from backend.src.core.dto.project import ProjectDetailResponse, LectureSummary, ProjectResponse
from backend.src.infrastructure.db.models.file_record import FileModel
from backend.src.infrastructure.db.repositories.project_repo import ProjectRepository


class GetProjectUseCase:
    """Handle single project retrieval."""

    def __init__(self, session: AsyncSession):
        self._repo = ProjectRepository(session)

    async def execute(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> ProjectDetailResponse:
        project = await self._repo.find_by_user_and_id(user_id, project_id)
        if not project:
            raise NotFoundError(message="Project not found")

        # Build lookup: lecture_id -> narrated_pptx URL
        lid_set = [l.id for l in project.lectures]
        pptx_urls: dict[uuid.UUID, str] = {}
        if lid_set:
            stmt = select(FileModel).where(
                FileModel.lecture_id.in_(lid_set),
                FileModel.file_type == "narrated_pptx",
            )
            result = await self._repo._session.execute(stmt)
            for fm in result.scalars().all():
                pptx_urls[fm.lecture_id] = f"/api/v1/files/{fm.id}"

        lectures = []
        for l in project.lectures:
            ls = LectureSummary.model_validate(l)
            ls.narrated_pptx_url = pptx_urls.get(l.id)
            lectures.append(ls)

        resp = ProjectDetailResponse.model_validate(project)
        resp.lectures = lectures
        resp.lecture_count = len(lectures)
        return resp
