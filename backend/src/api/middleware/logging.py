"""Request logging middleware with trace ID propagation."""

import time
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from backend.src.config.logging import generate_trace_id

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all requests with a trace ID and timing."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        trace_id = request.headers.get("X-Trace-ID") or generate_trace_id()
        request.state.trace_id = trace_id

        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        response.headers["X-Trace-ID"] = trace_id

        logger.info(
            "%s %s -> %s (%.1fms) [trace=%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            trace_id,
        )

        return response
