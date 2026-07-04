"""Voice profile Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateVoiceProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    consent: bool = False


class VoiceProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
