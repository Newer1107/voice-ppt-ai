"""Dependency injection providers for routes."""

from backend.src.config.settings import Settings, get_settings
from backend.src.core.ports.storage import StoragePort
from backend.src.infrastructure.storage.local_storage import LocalStorage


async def get_settings() -> Settings:
    """Provide the application settings singleton."""
    return get_settings()


async def get_storage() -> StoragePort:
    """Provide the storage implementation.

    Currently returns LocalStorage. In the future, this can switch
    based on settings.STORAGE_BACKEND to return S3Storage, etc.
    """
    settings = get_settings()
    return LocalStorage(root_path=settings.STORAGE_ROOT)
