"""Domain events for the lecture narration system."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class DomainEvent:
    """Base class for all domain events."""

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = ""


@dataclass
class LectureUploaded(DomainEvent):
    lecture_id: str = ""
    project_id: str = ""
    user_id: str = ""
    event_type: str = "lecture.uploaded"


@dataclass
class LectureProcessingStarted(DomainEvent):
    lecture_id: str = ""
    job_id: str = ""
    event_type: str = "lecture.processing_started"


@dataclass
class LectureProcessingCompleted(DomainEvent):
    lecture_id: str = ""
    narrated_pptx_path: str = ""
    event_type: str = "lecture.processing_completed"


@dataclass
class LectureProcessingFailed(DomainEvent):
    lecture_id: str = ""
    error_message: str = ""
    event_type: str = "lecture.processing_failed"


@dataclass
class NarrationGenerated(DomainEvent):
    lecture_id: str = ""
    slide_number: int = 0
    narration_id: str = ""
    event_type: str = "narration.generated"


@dataclass
class VoiceProfileCreated(DomainEvent):
    profile_id: str = ""
    user_id: str = ""
    event_type: str = "voice_profile.created"
