"""Security middleware - Headers and body size limits."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import environment


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)

        # Essential API security headers
        response.headers["X-Content-Type-Options"] = "nosniff"

        # HSTS for HTTPS enforcement (production only)
        if environment.IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Swagger/OpenAPI docs need CSP (dev only)
        if not environment.IS_PRODUCTION and request.url.path in (
            "/docs",
            "/redoc",
            "/openapi.json",
        ):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self'"
            )

        # Remove server header for security
        if "server" in response.headers:
            del response.headers["server"]

        return response


class BodySizeLimitMiddleware:
    """Reject requests exceeding maximum allowed body size."""

    def __init__(
        self,
        app: ASGIApp,
        max_body_size: int = 1_048_576,
    ) -> None:
        """
        Args:
            app: The downstream ASGI application.
            max_body_size: Maximum allowed body size in bytes (default: 1 MB).
        """
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Enforce body size limit on HTTP requests."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin1").lower(): v.decode("latin1") for k, v in scope.get("headers", [])
        }
        content_length = headers.get("content-length")

        # Check Content-Length header first
        if content_length and content_length.isdigit() and int(content_length) > self.max_body_size:
            await self._send_413(send)
            return

        # Track bytes read and if we've exceeded the limit
        bytes_read = 0
        body_exceeded = False

        async def limited_receive() -> Message:
            nonlocal bytes_read, body_exceeded
            message = await receive()

            if message["type"] == "http.request":
                body = message.get("body", b"")
                bytes_read += len(body)

                if bytes_read > self.max_body_size:
                    body_exceeded = True
                    # Return empty body with more_body=False to signal completion
                    # This allows us to send 413 before app processes
                    return {
                        "type": "http.request",
                        "body": b"",
                        "more_body": False,
                    }

            return message

        async def limited_send(message: Message) -> None:
            # If body was exceeded, intercept and send 413 instead
            if body_exceeded and message["type"] == "http.response.start":
                await self._send_413(send)
                return

            # Otherwise, pass through normally
            if not body_exceeded:
                await send(message)

        await self.app(scope, limited_receive, limited_send)

    @staticmethod
    async def _send_413(send: Send) -> None:
        """Send a 413 Payload Too Large response."""
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"msg":"Payload Too Large","data":{}}',
            }
        )
