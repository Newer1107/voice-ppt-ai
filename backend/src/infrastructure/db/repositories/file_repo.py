"""File record repository."""

import uuid
from typing import Optional

from sqlalchemy import select

from backend.src.infrastructure.db.models.file_record import FileModel
from backend.src.infrastructure.db.repositories.base import BaseRepository


class FileRepository(BaseRepository[FileModel]):
    """Repository for FileModel."""

    def __init__(self, session):
        super().__init__(session, FileModel)

    async def list_by_lecture(self, lecture_id: uuid.UUID) -> list[FileModel]:
        """List all files for a lecture."""
        stmt = (
            select(FileModel)
            .where(FileModel.lecture_id == lecture_id)
            .order_by(FileModel.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_user(self, user_id: uuid.UUID) -> list[FileModel]:
        """List all files for a user."""
        stmt = (
            select(FileModel)
            .where(FileModel.user_id == user_id)
            .order_by(FileModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_user_and_id(
        self, user_id: uuid.UUID, file_id: uuid.UUID
    ) -> Optional[FileModel]:
        """Find a file by user and file ID with lecture ownership."""
        stmt = select(FileModel).where(
            FileModel.id == file_id,
            FileModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
