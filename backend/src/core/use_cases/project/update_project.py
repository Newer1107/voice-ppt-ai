"""Update project use case."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import NotFoundError
from backend.src.core.dto.project import UpdateProjectRequest, ProjectResponse
from backend.src.infrastructure.db.repositories.project_repo import ProjectRepository


class UpdateProjectUseCase:
    """Handle project updates."""

    def __init__(self, session: AsyncSession):
        self._repo = ProjectRepository(session)

    async def execute(
        self, user_id: uuid.UUID, project_id: uuid.UUID, request: UpdateProjectRequest
    ) -> ProjectResponse:
        project = await self._repo.find_by_user_and_id(user_id, project_id)
        if not project:
            raise NotFoundError(message="Project not found")

        if request.title is not None:
            project.title = request.title
        if request.description is not None:
            project.description = request.description
        if request.status is not None:
            project.status = request.status

        project = await self._repo.update(project)
        return ProjectResponse.model_validate(project)
