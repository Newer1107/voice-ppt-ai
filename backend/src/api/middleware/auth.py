"""Authentication middleware that validates JWT tokens."""

import logging
from typing import Optional

from fastapi import Request
from jwt import PyJWTError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from backend.src.infrastructure.auth.jwt import decode_token

logger = logging.getLogger(__name__)

# Paths that don't require authentication
PUBLIC_PATHS = {"/api/v1/health", "/api/v1/auth/login", "/api/v1/auth/register", "/docs", "/openapi.json", "/redoc"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts and validates JWT from the Authorization header.

    Attaches `user_id` to `request.state` for use in route handlers.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip auth for public paths
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/ai/"):
            request.state.user_id = None
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = decode_token(token)
                request.state.user_id = payload.get("sub")
            except PyJWTError:
                logger.warning("Invalid token for path: %s", request.url.path)
                request.state.user_id = None
        else:
            request.state.user_id = None

        return await call_next(request)
