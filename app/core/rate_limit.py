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

if _env.IS_PRODUCTION:
    API_RATE_LIMIT = "60/minute"
    UPLOAD_RATE_LIMIT = "10/minute"
else:
    API_RATE_LIMIT = "1000/minute"
    UPLOAD_RATE_LIMIT = "1000/minute"


@limiter.limit(API_RATE_LIMIT)  # type: ignore[misc]
def _rate_limit_marker_default(request: Request) -> None:
    return None


@limiter.limit(UPLOAD_RATE_LIMIT)  # type: ignore[misc]
def _rate_limit_marker_upload(request: Request) -> None:
    return None


async def rate_limit_default(request: Request) -> None:
    """Apply the standard API rate limit."""
    limiter._check_request_limit(request, _rate_limit_marker_default, False)


async def rate_limit_upload(request: Request) -> None:
    """Apply the stricter upload rate limit."""
    limiter._check_request_limit(request, _rate_limit_marker_upload, False)


__all__ = [
    "API_RATE_LIMIT",
    "UPLOAD_RATE_LIMIT",
    "get_client_ip",
    "limiter",
    "rate_limit_default",
    "rate_limit_upload",
]
