"""User repository."""

import uuid
from typing import Optional

from sqlalchemy import select

from backend.src.infrastructure.db.models.user import UserModel
from backend.src.infrastructure.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[UserModel]):
    """Repository for UserModel with email-based queries."""

    def __init__(self, session):
        super().__init__(session, UserModel)

    async def find_by_email(self, email: str) -> Optional[UserModel]:
        """Find a user by email address."""
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        """Check if a user with the given email exists."""
        user = await self.find_by_email(email)
        return user is not None
