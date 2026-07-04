"""Get voice profile use case."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import NotFoundError
from backend.src.core.dto.voice import VoiceProfileResponse
from backend.src.infrastructure.db.repositories.voice_profile_repo import (
    VoiceProfileRepository,
)


class GetVoiceProfileUseCase:
    """Handle single voice profile retrieval."""

    def __init__(self, session: AsyncSession):
        self._repo = VoiceProfileRepository(session)

    async def execute(
        self, user_id: uuid.UUID, profile_id: uuid.UUID
    ) -> VoiceProfileResponse:
        profile = await self._repo.find_by_user_and_id(user_id, profile_id)
        if not profile:
            raise NotFoundError(message="Voice profile not found")
        return VoiceProfileResponse.model_validate(profile)
