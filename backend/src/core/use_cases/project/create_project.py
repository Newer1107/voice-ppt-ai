"""Create project use case."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.dto.project import CreateProjectRequest, ProjectResponse
from backend.src.infrastructure.db.models.project import ProjectModel
from backend.src.infrastructure.db.repositories.project_repo import ProjectRepository


class CreateProjectUseCase:
    """Handle project creation."""

    def __init__(self, session: AsyncSession):
        self._repo = ProjectRepository(session)

    async def execute(
        self, user_id: uuid.UUID, request: CreateProjectRequest
    ) -> ProjectResponse:
        project = ProjectModel(
            user_id=user_id,
            title=request.title,
            description=request.description,
        )
        project = await self._repo.add(project)
        return ProjectResponse.model_validate(project)
