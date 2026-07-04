"""Slide repository."""

import uuid
from typing import Optional

from sqlalchemy import select

from backend.src.infrastructure.db.models.slide import SlideModel
from backend.src.infrastructure.db.repositories.base import BaseRepository


class SlideRepository(BaseRepository[SlideModel]):
    """Repository for SlideModel."""

    def __init__(self, session):
        super().__init__(session, SlideModel)

    async def list_by_lecture(self, lecture_id: uuid.UUID) -> list[SlideModel]:
        """List all slides for a lecture, ordered by slide number."""
        stmt = (
            select(SlideModel)
            .where(SlideModel.lecture_id == lecture_id)
            .order_by(SlideModel.slide_number)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_insert(self, slides: list[SlideModel]) -> list[SlideModel]:
        """Insert multiple slides at once."""
        self._session.add_all(slides)
        await self._session.flush()
        return slides
