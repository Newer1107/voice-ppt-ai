"""Pytest configuration and fixtures for testing."""

import asyncio
import uuid
import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.main import create_app
from backend.src.config.settings import get_settings
from backend.src.infrastructure.db.models import Base
from backend.src.infrastructure.db.session import get_db
from backend.src.core.ports.storage import StoragePort
from backend.src.infrastructure.storage.local_storage import LocalStorage
from backend.src.api.dependencies.providers import get_storage

# Use SQLite for testing (fast, no external deps)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
_TEST_TMP = tempfile.mkdtemp(prefix="lecture_narrator_test_")
TEST_STORAGE_ROOT = _TEST_TMP


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_maker() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def storage() -> StoragePort:
    """Create a temporary storage instance."""
    storage = LocalStorage(root_path=TEST_STORAGE_ROOT)
    yield storage
    # Cleanup
    import shutil
    if Path(TEST_STORAGE_ROOT).exists():
        shutil.rmtree(TEST_STORAGE_ROOT)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a FastAPI test client."""
    app = create_app()

    # Override DB dependency
    async def override_get_db():
        yield db_session

    # Override storage dependency
    storage = LocalStorage(root_path=TEST_STORAGE_ROOT)
    async def override_get_storage():
        return storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = override_get_storage

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
