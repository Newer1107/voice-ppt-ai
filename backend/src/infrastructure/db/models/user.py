"""User ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.infrastructure.db.models.base import Base, TimestampMixin


class UserModel(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    projects: Mapped[list["ProjectModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    voice_profiles: Mapped[list["VoiceProfileModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    files: Mapped[list["FileModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
