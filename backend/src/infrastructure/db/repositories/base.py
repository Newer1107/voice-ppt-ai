"""Generic base repository with common CRUD operations."""

import uuid
from typing import Generic, Optional, TypeVar

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.infrastructure.db.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic repository with standard CRUD operations."""

    def __init__(self, session: AsyncSession, model_class: type[ModelType]) -> None:
        self._session = session
        self._model = model_class

    async def get(self, id: uuid.UUID) -> Optional[ModelType]:
        """Get a single entity by ID."""
        stmt = select(self._model).where(self._model.id == id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self, skip: int = 0, limit: int = 100, **filters
    ) -> list[ModelType]:
        """List entities with optional filters."""
        stmt = select(self._model).offset(skip).limit(limit)
        for field, value in filters.items():
            if hasattr(self._model, field):
                stmt = stmt.where(getattr(self._model, field) == value)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, entity: ModelType) -> ModelType:
        """Add a new entity to the session."""
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def update(self, entity: ModelType) -> ModelType:
        """Update an existing entity."""
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def delete(self, entity: ModelType) -> None:
        """Delete an entity from the session."""
        await self._session.delete(entity)
        await self._session.flush()

    async def count(self, **filters) -> int:
        """Count entities with optional filters."""
        stmt = select(func.count()).select_from(self._model)
        for field, value in filters.items():
            if hasattr(self._model, field):
                stmt = stmt.where(getattr(self._model, field) == value)
        result = await self._session.execute(stmt)
        return result.scalar_one()
