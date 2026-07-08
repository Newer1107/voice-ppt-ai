"""Project-related Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CreateProjectRequest(BaseModel):
    title: str
    description: Optional[str] = None


class UpdateProjectRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class LectureSummary(BaseModel):
    id: uuid.UUID
    title: str
    input_type: str
    status: str
    duration_seconds: Optional[int] = None
    narrated_pptx_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: str
    lecture_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: str
    lecture_count: int = 0
    lectures: list[LectureSummary] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int
