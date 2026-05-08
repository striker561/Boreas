"""Middleware module - Observability and security middleware."""

from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.middleware.observability import LogMiddleware, RequestIDMiddleware
from app.core.middleware.security import BodySizeLimitMiddleware, SecurityHeadersMiddleware

__all__ = [
    "BodySizeLimitMiddleware",
    "LogMiddleware",
    "RequestIDMiddleware",
    "SecurityHeadersMiddleware",
    "TrustedHostMiddleware",
]
