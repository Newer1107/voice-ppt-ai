"""Application configuration via Pydantic Settings."""

from functools import lru_cache
from typing import List

from pydantic import PostgresDsn, RedisDsn, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI Lecture Narrator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    SECRET_KEY: str = "change-me-in-production"

    # Database
    DATABASE_URL: PostgresDsn = "postgresql+asyncpg://app_user:devpassword@localhost:5432/lecture_narrator"  # type: ignore
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: RedisDsn = "redis://:devpassword@localhost:6379/0"  # type: ignore
    REDIS_RESULT_URL: RedisDsn = "redis://:devpassword@localhost:6379/1"  # type: ignore
    REDIS_PASSWORD: str = "devpassword"

    # JWT
    JWT_SECRET_KEY: str = "change-me-jwt-secret-key-64-chars-min"
    JWT_ACCESS_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    # AI Server (unified GPU service — single endpoint for all models)
    AI_SERVICE_URL: str = "http://gpu-service:8001"
    AI_TRANSCRIPTION_URL: str = "http://transcription:8001"  # kept for backward compat
    AI_LLM_URL: str = "http://llm:8002"                      # kept for backward compat
    AI_TTS_URL: str = "http://tts:8003"                      # kept for backward compat
    AI_API_KEY: str = ""

    # Storage — all paths default to project-root/data/*
    STORAGE_BACKEND: str = "local"
    STORAGE_ROOT: str = "data/storage"
    DATA_DIR: str = "data"
    VOICE_EMBEDDINGS_DIR: str = "data/voice_embeddings"
    CACHE_DIR: str = "data/cache"
    MODELS_DIR: str = "data/models"
    TEMP_DIR: str = "data/temp"

    # Upload Limits
    MAX_VIDEO_SIZE_BYTES: int = 2_147_483_648  # 2GB
    MAX_AUDIO_SIZE_BYTES: int = 524_288_000  # 500MB
    MAX_PPTX_SIZE_BYTES: int = 209_715_200  # 200MB

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Models
    WHISPER_MODEL_SIZE: str = "large-v3"
    VLLM_MODEL: str = "Qwen/Qwen3-8B"
    TTS_SAMPLE_RATE: int = 24000

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
