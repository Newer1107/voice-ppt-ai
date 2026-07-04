"""FastAPI application entry point."""

import logging

from fastapi import FastAPI

from backend.src.api.errors.handlers import register_error_handlers
from backend.src.api.middleware.cors import setup_cors
from backend.src.api.middleware.logging import LoggingMiddleware
from backend.src.api.routes.auth import router as auth_router
from backend.src.api.routes.projects import router as project_router
from backend.src.api.routes.lectures import router as lecture_router
from backend.src.api.routes.voice import router as voice_router
from backend.src.api.routes.files import router as file_router
from backend.src.api.routes.health import router as health_router
from backend.src.config.logging import setup_logging
from backend.src.config.settings import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    # Configure structured logging
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        description="AI Lecture Narration Generator API",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # Error handling
    register_error_handlers(app)

    # CORS
    setup_cors(app)

    # Middleware
    app.add_middleware(LoggingMiddleware)

    # Routes
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(project_router)
    app.include_router(lecture_router)
    app.include_router(voice_router)
    app.include_router(file_router)

    @app.on_event("startup")
    async def startup():
        logger.info(
            "Starting %s v%s (%s)",
            settings.APP_NAME,
            settings.APP_VERSION,
            settings.ENVIRONMENT,
        )

    @app.on_event("shutdown")
    async def shutdown():
        logger.info("Shutting down %s", settings.APP_NAME)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
