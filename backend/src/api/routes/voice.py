"""Voice profile routes."""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies.auth import get_current_user
from backend.src.api.dependencies.providers import get_storage
from backend.src.core.dto.voice import (
    CreateVoiceProfileRequest,
    VoiceProfileResponse,
)
from backend.src.core.ports.storage import StoragePort
from backend.src.core.use_cases.voice.create_voice_profile import (
    CreateVoiceProfileUseCase,
)
from backend.src.core.use_cases.voice.list_voice_profiles import (
    ListVoiceProfilesUseCase,
)
from backend.src.core.use_cases.voice.get_voice_profile import GetVoiceProfileUseCase
from backend.src.core.use_cases.voice.delete_voice_profile import (
    DeleteVoiceProfileUseCase,
)
from backend.src.infrastructure.db.models.user import UserModel
from backend.src.infrastructure.db.session import get_db

router = APIRouter(
    prefix="/api/v1/voice-profiles",
    tags=["Voice Profiles"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[VoiceProfileResponse])
async def list_voice_profiles(
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all voice profiles for the current user."""
    use_case = ListVoiceProfilesUseCase(session)
    return await use_case.execute(user_id=current_user.id)


@router.post("", response_model=VoiceProfileResponse, status_code=201)
async def create_voice_profile(
    name: str = Form(...),
    consent: bool = Form(...),
    audio_file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StoragePort = Depends(get_storage),
):
    """Create a new voice profile from an audio sample."""
    audio_content = await audio_file.read()
    request = CreateVoiceProfileRequest(name=name, consent=consent)
    use_case = CreateVoiceProfileUseCase(session, storage)
    return await use_case.execute(
        user_id=current_user.id,
        request=request,
        audio_filename=audio_file.filename or "sample.wav",
        audio_content=audio_content,
    )


@router.get("/{profile_id}", response_model=VoiceProfileResponse)
async def get_voice_profile(
    profile_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get a single voice profile."""
    use_case = GetVoiceProfileUseCase(session)
    return await use_case.execute(user_id=current_user.id, profile_id=profile_id)


@router.delete("/{profile_id}", status_code=204)
async def delete_voice_profile(
    profile_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StoragePort = Depends(get_storage),
):
    """Delete a voice profile."""
    use_case = DeleteVoiceProfileUseCase(session, storage)
    return await use_case.execute(user_id=current_user.id, profile_id=profile_id)
