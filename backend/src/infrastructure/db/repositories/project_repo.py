"""Project repository."""

import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from backend.src.infrastructure.db.models.project import ProjectModel
from backend.src.infrastructure.db.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[ProjectModel]):
    """Repository for ProjectModel with user-scoped queries."""

    def __init__(self, session):
        super().__init__(session, ProjectModel)

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[ProjectModel], int]:
        """List projects for a user with pagination.

        Returns (projects, total_count).
        """
        # Count
        count_stmt = select(func.count()).select_from(ProjectModel).where(
            ProjectModel.user_id == user_id
        )
        if status:
            count_stmt = count_stmt.where(ProjectModel.status == status)
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        # Query
        stmt = (
            select(ProjectModel)
            .where(ProjectModel.user_id == user_id)
            .options(selectinload(ProjectModel.lectures))
            .offset(skip)
            .limit(limit)
            .order_by(ProjectModel.created_at.desc())
        )
        if status:
            stmt = stmt.where(ProjectModel.status == status)
        result = await self._session.execute(stmt)
        projects = list(result.scalars().all())

        return projects, total

    async def find_by_user_and_id(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> Optional[ProjectModel]:
        """Find a project by user and project ID."""
        stmt = (
            select(ProjectModel)
            .where(
                ProjectModel.id == project_id,
                ProjectModel.user_id == user_id,
            )
            .options(selectinload(ProjectModel.lectures))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
