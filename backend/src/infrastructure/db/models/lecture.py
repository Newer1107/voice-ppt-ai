"""Lecture ORM model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.infrastructure.db.models.base import Base, TimestampMixin


class LectureModel(TimestampMixin, Base):
    __tablename__ = "lectures"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    input_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'video' | 'audio' | 'live'
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False, index=True
    )
    video_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pptx_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    narrated_pptx_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voice_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("voice_profiles.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    project: Mapped["ProjectModel"] = relationship(back_populates="lectures")
    voice_profile: Mapped[Optional["VoiceProfileModel"]] = relationship(
        back_populates="lectures"
    )
    slides: Mapped[list["SlideModel"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )
    transcript_segments: Mapped[list["TranscriptSegmentModel"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )
    narrations: Mapped[list["NarrationModel"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["JobModel"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )
    files: Mapped[list["FileModel"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )
