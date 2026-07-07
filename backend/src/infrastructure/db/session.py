"""Database session factory and FastAPI dependency."""

from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session as SyncSession
from sqlalchemy.pool import NullPool

from backend.src.config.settings import get_settings

settings = get_settings()

# Async engine (used by FastAPI routes)
engine = create_async_engine(
    str(settings.DATABASE_URL),
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Sync engine & session maker (used by Celery workers — orchestrator is sync)
_sync_engine = create_engine(
    str(settings.DATABASE_URL).replace("postgresql+asyncpg://", "postgresql+psycopg2://"),
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)
sync_session_maker = None  # created on first use (lazy import avoids psycopg2 requirement)


def get_sync_session() -> SyncSession:
    """Create a sync DB session for Celery workers."""
    global sync_session_maker
    if sync_session_maker is None:
        from sqlalchemy.orm import sessionmaker as SyncSessionMaker
        global sync_session_maker
        sync_session_maker = SyncSessionMaker(
            bind=_sync_engine,
            expire_on_commit=False,
            autoflush=False,
        )
    return sync_session_maker()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a DB session, rolls back on exception.

    Use this for background tasks and scripts.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a session and handles rollback.

    Usage:
        @router.get("/items")
        async def list_items(session: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
