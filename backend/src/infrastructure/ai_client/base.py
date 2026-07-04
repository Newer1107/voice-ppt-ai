"""Base HTTP client for AI server communication."""

import logging
from typing import Any, Optional

import httpx

from backend.src.config.settings import get_settings

logger = logging.getLogger(__name__)


class BaseAIClient:
    """Base class for AI service HTTP clients.

    Provides common HTTP methods with API key authentication,
    error handling, and logging.
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 120):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    async def _get(self, path: str) -> dict[str, Any]:
        """Send a GET request to the AI service."""
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                url, headers=self._build_headers()
            )
            response.raise_for_status()
            return response.json()

    async def _post(
        self,
        path: str,
        json_data: Optional[dict] = None,
        files: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Send a POST request to the AI service."""
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                json=json_data,
                files=files,
                headers=self._build_headers() if not files else {"X-API-Key": self._api_key},
            )
            response.raise_for_status()
            return response.json()

    async def _post_binary(
        self,
        path: str,
        data: bytes,
        headers: dict[str, str],
    ) -> bytes:
        """Send a POST request that returns binary data."""
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                content=data,
                headers={**self._build_headers(), **headers},
            )
            response.raise_for_status()
            return response.content
