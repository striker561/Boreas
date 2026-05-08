"""Redis-backed storage helpers used by the core layer."""

from app.core.storage.dependency import (
    get_redis_cache,
)
from app.core.storage.redis import RedisCache

__all__ = [
    "RedisCache",
    "get_redis_cache",
]
