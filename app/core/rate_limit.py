"""IP-based rate limiting for the current API surface."""

from fastapi import Request
from slowapi import Limiter

from app.core.config.environment import get_environment

_env = get_environment()


def get_client_ip(request: Request) -> str:
    """Resolve the client IP, preferring proxy headers when present."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # Try X-Real-IP (Nginx, Cloudflare)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Try Cloudflare-specific header
    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    if cf_connecting_ip:
        return cf_connecting_ip.strip()

    # Fallback to direct connection (development/no proxy)
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(
    key_func=get_client_ip,
    storage_uri=_env.REDIS_URL,
    strategy="moving-window",
    headers_enabled=True,
)

API_RATE_LIMIT = _env.API_RATE_LIMIT
UPLOAD_RATE_LIMIT = _env.UPLOAD_RATE_LIMIT


__all__ = [
    "API_RATE_LIMIT",
    "UPLOAD_RATE_LIMIT",
    "get_client_ip",
    "limiter",
]
