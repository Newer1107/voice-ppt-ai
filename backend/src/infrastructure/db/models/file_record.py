"""File record ORM model for tracking stored files."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.infrastructure.db.models.base import Base


class FileModel(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lecture_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("lectures.id", ondelete="SET NULL"), nullable=True, index=True
    )
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="files")
    lecture: Mapped[Optional["LectureModel"]] = relationship(back_populates="files")
