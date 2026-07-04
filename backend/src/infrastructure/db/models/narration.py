"""Narration ORM model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.infrastructure.db.models.base import Base, TimestampMixin


class NarrationModel(TimestampMixin, Base):
    __tablename__ = "narrations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slide_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("slides.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lecture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True
    )
    script_text: Mapped[str] = mapped_column(Text, nullable=False)
    audio_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    slide: Mapped["SlideModel"] = relationship(back_populates="narration")
    lecture: Mapped["LectureModel"] = relationship(back_populates="narrations")
