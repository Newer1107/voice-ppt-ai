"""Delete voice profile use case."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import NotFoundError
from backend.src.core.ports.storage import StoragePort
from backend.src.infrastructure.db.repositories.voice_profile_repo import (
    VoiceProfileRepository,
)


class DeleteVoiceProfileUseCase:
    """Handle voice profile deletion."""

    def __init__(self, session: AsyncSession, storage: StoragePort):
        self._repo = VoiceProfileRepository(session)
        self._storage = storage

    async def execute(self, user_id: uuid.UUID, profile_id: uuid.UUID) -> None:
        profile = await self._repo.find_by_user_and_id(user_id, profile_id)
        if not profile:
            raise NotFoundError(message="Voice profile not found")

        # Clean up stored audio
        if profile.sample_audio_path:
            await self._storage.delete(profile.sample_audio_path)

        await self._repo.delete(profile)
