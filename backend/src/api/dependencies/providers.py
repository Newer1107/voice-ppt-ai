"""Dependency injection providers for routes."""

from backend.src.config.settings import Settings, get_settings as get_app_settings
from backend.src.core.ports.storage import StoragePort
from backend.src.infrastructure.storage.local_storage import LocalStorage


async def get_settings() -> Settings:
    return get_app_settings()


async def get_storage() -> StoragePort:
    settings = get_app_settings()
    return LocalStorage(root_path=settings.STORAGE_ROOT)
