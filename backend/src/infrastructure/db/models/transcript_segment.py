"""Transcript Segment ORM model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.infrastructure.db.models.base import Base


class TranscriptSegmentModel(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lecture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slide_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("slides.id", ondelete="SET NULL"), nullable=True, index=True
    )
    segment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speaker: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "lecture_id", "segment_number", name="uq_lecture_segment"
        ),
    )

    # Relationships
    lecture: Mapped["LectureModel"] = relationship(back_populates="transcript_segments")
    slide: Mapped[Optional["SlideModel"]] = relationship(back_populates="transcript_segments")
