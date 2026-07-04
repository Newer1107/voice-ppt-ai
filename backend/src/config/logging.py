"""Structured JSON logging configuration."""

import logging
import sys
import uuid
from datetime import datetime, timezone

import structlog


def setup_logging() -> None:
    """Configure structured JSON logging for the application.

    Uses structlog to emit JSON-formatted logs with:
    - ISO 8601 timestamps
    - Log level
    - Service name
    - Trace ID (for request correlation)
    - Message
    - Extra context
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set up root logger to capture standard library logs too
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer() if sys.stdout.isatty()
        else structlog.processors.JSONRenderer(),
    ))
    root_logger.addHandler(handler)

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def generate_trace_id() -> str:
    """Generate a unique trace ID for request correlation."""
    return uuid.uuid4().hex[:16]
