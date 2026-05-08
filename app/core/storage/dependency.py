"""Redis cache dependencies for the application."""

from app.core.config import environment
from app.core.storage.redis import RedisCache

_redis_cache: RedisCache | None = None


def get_redis_cache() -> RedisCache:
    """Get Redis cache (initialized once)."""
    global _redis_cache
    if _redis_cache is None:
        from app.core.storage.redis import RedisCache

        _redis_cache = RedisCache(environment.REDIS_URL)
    return _redis_cache


def get_redis() -> RedisCache:
    """FastAPI dependency for Redis cache."""
    return get_redis_cache()
