"""Delete project use case."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import NotFoundError
from backend.src.infrastructure.db.repositories.project_repo import ProjectRepository


class DeleteProjectUseCase:
    """Handle project deletion."""

    def __init__(self, session: AsyncSession):
        self._repo = ProjectRepository(session)

    async def execute(self, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
        project = await self._repo.find_by_user_and_id(user_id, project_id)
        if not project:
            raise NotFoundError(message="Project not found")
        await self._repo.delete(project)
