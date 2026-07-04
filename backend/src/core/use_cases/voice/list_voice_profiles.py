"""List voice profiles use case."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.dto.voice import VoiceProfileResponse
from backend.src.infrastructure.db.repositories.voice_profile_repo import (
    VoiceProfileRepository,
)


class ListVoiceProfilesUseCase:
    """Handle listing voice profiles for a user."""

    def __init__(self, session: AsyncSession):
        self._repo = VoiceProfileRepository(session)

    async def execute(self, user_id: uuid.UUID) -> list[VoiceProfileResponse]:
        profiles = await self._repo.list_by_user(user_id)
        return [
            VoiceProfileResponse.model_validate(p) for p in profiles
        ]
