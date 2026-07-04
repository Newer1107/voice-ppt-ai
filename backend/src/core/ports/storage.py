"""Storage port interface — abstract filesystem operations."""

from abc import ABC, abstractmethod


class StoragePort(ABC):
    """Abstract port for file storage operations.

    Implementations: LocalStorage, S3Storage, etc.
    """

    @abstractmethod
    async def store(self, file_path: str, content: bytes) -> str:
        """Store content at the given path. Returns the storage path."""
        ...

    @abstractmethod
    async def retrieve(self, storage_path: str) -> bytes:
        """Retrieve content from the given storage path."""
        ...

    @abstractmethod
    async def delete(self, storage_path: str) -> None:
        """Delete content at the given storage path."""
        ...

    @abstractmethod
    async def exists(self, storage_path: str) -> bool:
        """Check if content exists at the given storage path."""
        ...

    @abstractmethod
    async def get_size(self, storage_path: str) -> int:
        """Get the size of content at the given storage path in bytes."""
        ...
