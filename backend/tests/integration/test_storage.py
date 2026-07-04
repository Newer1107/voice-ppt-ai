"""Storage integration tests."""

import tempfile
from pathlib import Path

import pytest

from backend.src.infrastructure.storage.local_storage import LocalStorage


@pytest.fixture
def storage():
    """Create a temporary local storage instance."""
    tmp_dir = tempfile.mkdtemp()
    store = LocalStorage(root_path=tmp_dir)
    yield store
    import shutil
    shutil.rmtree(tmp_dir)


@pytest.mark.asyncio
async def test_store_and_retrieve(storage: LocalStorage):
    """S1: Store content and retrieve it."""
    stored = await storage.store("test/file.txt", b"Hello World")
    assert stored == "test/file.txt"

    content = await storage.retrieve("test/file.txt")
    assert content == b"Hello World"


@pytest.mark.asyncio
async def test_store_and_exists(storage: LocalStorage):
    """S2: Check file existence."""
    assert not await storage.exists("test/nonexistent.txt")
    await storage.store("test/exists.txt", b"data")
    assert await storage.exists("test/exists.txt")


@pytest.mark.asyncio
async def test_delete(storage: LocalStorage):
    """S3: Delete a file."""
    await storage.store("test/delete_me.txt", b"data")
    assert await storage.exists("test/delete_me.txt")
    await storage.delete("test/delete_me.txt")
    assert not await storage.exists("test/delete_me.txt")


@pytest.mark.asyncio
async def test_get_size(storage: LocalStorage):
    """S4: Get file size."""
    await storage.store("test/size.txt", b"12345")
    size = await storage.get_size("test/size.txt")
    assert size == 5


@pytest.mark.asyncio
async def test_path_traversal_prevention(storage: LocalStorage):
    """S5: Path traversal attacks should be blocked."""
    with pytest.raises(PermissionError):
        await storage.store("../../etc/passwd", b"hack")


@pytest.mark.asyncio
async def test_nested_directories(storage: LocalStorage):
    """S6: Nested directory creation."""
    stored = await storage.store("a/b/c/d/file.txt", b"nested")
    assert stored == "a/b/c/d/file.txt"
    assert await storage.exists("a/b/c/d/file.txt")
