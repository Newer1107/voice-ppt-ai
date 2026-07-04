"""Slide ORM model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.infrastructure.db.models.base import Base


class SlideModel(Base):
    __tablename__ = "slides"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lecture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slide_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    slide_layout: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("lecture_id", "slide_number", name="uq_lecture_slide"),
    )

    # Relationships
    lecture: Mapped["LectureModel"] = relationship(back_populates="slides")
    transcript_segments: Mapped[list["TranscriptSegmentModel"]] = relationship(
        back_populates="slide"
    )
    narration: Mapped[Optional["NarrationModel"]] = relationship(
        back_populates="slide", cascade="all, delete-orphan", uselist=False
    )
