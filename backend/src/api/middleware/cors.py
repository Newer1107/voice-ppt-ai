"""CORS middleware setup."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.src.config.settings import get_settings


def setup_cors(app: FastAPI) -> None:
    """Configure CORS middleware from settings."""
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
