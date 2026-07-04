"""Job repository."""

import uuid
from typing import Optional

from sqlalchemy import select

from backend.src.infrastructure.db.models.job import JobModel
from backend.src.infrastructure.db.repositories.base import BaseRepository


class JobRepository(BaseRepository[JobModel]):
    """Repository for JobModel."""

    def __init__(self, session):
        super().__init__(session, JobModel)

    async def list_by_lecture(self, lecture_id: uuid.UUID) -> list[JobModel]:
        """List all jobs for a lecture."""
        stmt = (
            select(JobModel)
            .where(JobModel.lecture_id == lecture_id)
            .order_by(JobModel.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_celery_id(self, celery_id: str) -> Optional[JobModel]:
        """Find a job by its Celery task ID."""
        stmt = select(JobModel).where(JobModel.celery_id == celery_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
