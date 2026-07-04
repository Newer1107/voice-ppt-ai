"""Structured error handling for the API."""

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application error with structured fields."""

    def __init__(
        self,
        status_code: int = 500,
        code: str = "INTERNAL_ERROR",
        message: str = "An unexpected error occurred",
        details: Optional[dict[str, Any]] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", details: Optional[dict] = None):
        super().__init__(status_code=404, code="NOT_FOUND", message=message, details=details)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Not authenticated", details: Optional[dict] = None):
        super().__init__(status_code=401, code="UNAUTHORIZED", message=message, details=details)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Not authorized", details: Optional[dict] = None):
        super().__init__(status_code=403, code="FORBIDDEN", message=message, details=details)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource already exists", details: Optional[dict] = None):
        super().__init__(status_code=409, code="CONFLICT", message=message, details=details)


class FileTooLargeError(AppError):
    def __init__(self, message: str = "File too large", details: Optional[dict] = None):
        super().__init__(status_code=413, code="FILE_TOO_LARGE", message=message, details=details)


class UnsupportedFileTypeError(AppError):
    def __init__(self, message: str = "Unsupported file type", details: Optional[dict] = None):
        super().__init__(status_code=415, code="UNSUPPORTED_FILE_TYPE", message=message, details=details)


class BadRequestError(AppError):
    def __init__(self, message: str = "Bad request", details: Optional[dict] = None):
        super().__init__(status_code=400, code="BAD_REQUEST", message=message, details=details)


def _build_error_response(
    code: str,
    message: str,
    status_code: int,
    details: Optional[dict] = None,
) -> JSONResponse:
    """Build a structured error response."""
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "status_code": status_code,
        }
    }
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle custom AppError exceptions."""
    return _build_error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic/FastAPI validation errors."""
    errors = {}
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err.get("loc", []))
        errors[field] = err.get("msg", "Invalid value")
    return _build_error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=422,
        details={"fields": errors},
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions (500)."""
    logger.exception("Unhandled exception: %s", exc)
    return _build_error_response(
        code="INTERNAL_ERROR",
        message="An internal server error occurred",
        status_code=500,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_error_handler)
