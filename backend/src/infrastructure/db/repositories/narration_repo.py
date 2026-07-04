"""Narration repository."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.src.infrastructure.db.models.narration import NarrationModel
from backend.src.infrastructure.db.repositories.base import BaseRepository


class NarrationRepository(BaseRepository[NarrationModel]):
    """Repository for NarrationModel."""

    def __init__(self, session):
        super().__init__(session, NarrationModel)

    async def list_by_lecture(self, lecture_id: uuid.UUID) -> list[NarrationModel]:
        """List all narrations for a lecture."""
        stmt = (
            select(NarrationModel)
            .where(NarrationModel.lecture_id == lecture_id)
            .order_by(NarrationModel.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_slide(self, slide_id: uuid.UUID) -> Optional[NarrationModel]:
        """Find narration for a specific slide."""
        stmt = select(NarrationModel).where(NarrationModel.slide_id == slide_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
