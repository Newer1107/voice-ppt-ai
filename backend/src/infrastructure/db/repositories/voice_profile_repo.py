"""Voice profile repository."""

import uuid
from typing import Optional

from sqlalchemy import select

from backend.src.infrastructure.db.models.voice_profile import VoiceProfileModel
from backend.src.infrastructure.db.repositories.base import BaseRepository


class VoiceProfileRepository(BaseRepository[VoiceProfileModel]):
    """Repository for VoiceProfileModel."""

    def __init__(self, session):
        super().__init__(session, VoiceProfileModel)

    async def list_by_user(self, user_id: uuid.UUID) -> list[VoiceProfileModel]:
        """List all voice profiles for a user."""
        stmt = (
            select(VoiceProfileModel)
            .where(VoiceProfileModel.user_id == user_id)
            .order_by(VoiceProfileModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_user_and_id(
        self, user_id: uuid.UUID, profile_id: uuid.UUID
    ) -> Optional[VoiceProfileModel]:
        """Find a voice profile by user and profile ID."""
        stmt = select(VoiceProfileModel).where(
            VoiceProfileModel.id == profile_id,
            VoiceProfileModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
