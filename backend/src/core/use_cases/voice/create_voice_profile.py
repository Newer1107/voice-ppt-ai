"""Create voice profile use case."""

import uuid
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import BadRequestError
from backend.src.core.dto.voice import CreateVoiceProfileRequest, VoiceProfileResponse
from backend.src.core.ports.storage import StoragePort
from backend.src.infrastructure.db.models.voice_profile import VoiceProfileModel
from backend.src.infrastructure.db.repositories.voice_profile_repo import (
    VoiceProfileRepository,
)
from backend.src.infrastructure.storage.local_storage import StoragePaths

logger = logging.getLogger(__name__)


class CreateVoiceProfileUseCase:
    """Handle voice profile creation from uploaded audio sample."""

    def __init__(self, session: AsyncSession, storage: StoragePort):
        self._repo = VoiceProfileRepository(session)
        self._storage = storage

    async def execute(
        self,
        user_id: uuid.UUID,
        request: CreateVoiceProfileRequest,
        audio_filename: str,
        audio_content: bytes,
    ) -> VoiceProfileResponse:
        if not request.consent:
            raise BadRequestError(
                message="You must consent to voice cloning",
                details={"consent": "This field is required"},
            )

        # Validate audio length (simple check: reasonable size for 30s+)
        if len(audio_content) < 240_000:  # ~30s of 16-bit 16kHz mono
            logger.warning(
                "Voice sample too short: %d bytes for user %s",
                len(audio_content),
                user_id,
            )

        # Store audio sample
        storage_path = str(
            StoragePaths.voice_sample(str(user_id), str(uuid.uuid4()))
        )
        stored_path = await self._storage.store(storage_path, audio_content)

        # Create profile record
        profile = VoiceProfileModel(
            user_id=user_id,
            name=request.name,
            sample_audio_path=stored_path,
            status="pending",
        )
        profile = await self._repo.add(profile)

        logger.info(
            "Voice profile created: id=%s user=%s name=%s",
            profile.id,
            user_id,
            request.name,
        )

        # Note: In production, this would trigger an async job to process
        # the voice sample (clone the voice). For MVP, set to 'ready'.
        profile.status = "ready"
        await self._repo.update(profile)

        return VoiceProfileResponse.model_validate(profile)
