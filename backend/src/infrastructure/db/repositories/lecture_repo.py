"""Lecture repository."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.src.infrastructure.db.models.lecture import LectureModel
from backend.src.infrastructure.db.repositories.base import BaseRepository


class LectureRepository(BaseRepository[LectureModel]):
    """Repository for LectureModel."""

    def __init__(self, session):
        super().__init__(session, LectureModel)

    async def list_by_project(self, project_id: uuid.UUID) -> list[LectureModel]:
        """List all lectures in a project."""
        stmt = (
            select(LectureModel)
            .where(LectureModel.project_id == project_id)
            .order_by(LectureModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_project_and_id(
        self, project_id: uuid.UUID, lecture_id: uuid.UUID
    ) -> Optional[LectureModel]:
        """Find a lecture by project and lecture ID with slides and narrations."""
        stmt = (
            select(LectureModel)
            .where(
                LectureModel.id == lecture_id,
                LectureModel.project_id == project_id,
            )
            .options(
                selectinload(LectureModel.slides),
                selectinload(LectureModel.narrations),
                selectinload(LectureModel.jobs),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        lecture_id: uuid.UUID,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Update lecture status."""
        lecture = await self.get(lecture_id)
        if lecture:
            lecture.status = status
            if error_message:
                lecture.error_message = error_message
            await self._session.flush()
