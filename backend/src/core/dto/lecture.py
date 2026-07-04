"""Lecture-related Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class UploadLectureResponse(BaseModel):
    id: uuid.UUID
    title: str
    input_type: str
    status: str
    job_id: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NarrationSummaryResponse(BaseModel):
    id: uuid.UUID
    script_text: str
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class SlideNarrationResponse(BaseModel):
    id: uuid.UUID
    slide_number: int
    raw_text: Optional[str] = None
    narration: Optional[NarrationSummaryResponse] = None

    model_config = ConfigDict(from_attributes=True)


class LectureDetailResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    input_type: str
    status: str
    duration_seconds: Optional[int] = None
    slides: list[SlideNarrationResponse] = []
    transcript_url: Optional[str] = None
    narrated_pptx_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobSummaryResponse(BaseModel):
    id: uuid.UUID
    job_type: str
    status: str
    progress: float

    model_config = ConfigDict(from_attributes=True)


class LectureStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    progress: float = 0.0
    current_stage: Optional[str] = None
    jobs: list[JobSummaryResponse] = []
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
