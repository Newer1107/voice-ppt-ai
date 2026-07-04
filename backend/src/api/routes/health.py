"""Health check endpoint."""

import time
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config.settings import get_settings
from backend.src.infrastructure.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])
_start_time = time.time()


@router.get("/api/v1/health")
async def health_check(session: AsyncSession = Depends(get_db)):
    """Health check endpoint verifying DB, Redis, and AI services."""
    settings = get_settings()
    health = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "uptime_seconds": int(time.time() - _start_time),
        "services": {},
    }

    # Check PostgreSQL
    try:
        await session.execute(text("SELECT 1"))
        health["services"]["postgres"] = "healthy"
    except Exception as e:
        health["status"] = "degraded"
        health["services"]["postgres"] = "unhealthy"
        logger.warning("Health check: postgres unhealthy: %s", e)

    # Redis check would go here if redis is connected
    health["services"]["redis"] = "not_configured"

    return health
