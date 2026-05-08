"""Observability middleware - Request ID tracking and logging."""

import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import logger

# Context variable for request ID
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate or extract request IDs for distributed tracing."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Extract or generate request ID
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))

        # Store in context for access in logging
        request_id_ctx.set(request_id)

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class LogMiddleware(BaseHTTPMiddleware):
    """Log all HTTP requests with timing and structured data."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.time()

        response = await call_next(request)

        process_time = time.time() - start

        # Get client IP (check X-Forwarded-For for proxies)
        client_ip = request.headers.get("x-forwarded-for")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = "unknown"

        # Get user agent
        user_agent = request.headers.get("user-agent", "unknown")

        # Get user ID if authenticated (from request.state if available)
        user_id = getattr(request.state, "unique_id", None)

        # Log request details
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code}",
            method=request.method,
            url=request.url.path,
            status_code=response.status_code,
            request_id=request_id_ctx.get(""),
            process_time=round(process_time, 4),
            client_ip=client_ip,
            user_agent=user_agent,
            user_id=user_id,
        )

        return response
