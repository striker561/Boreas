"""
arq job-queue pool — managed as a core infrastructure concern.

Initialized once on app startup via lifespan; closed on shutdown.
Consumer code (e.g. EmailService) calls get_arq_pool() as a
dependency — it never manages the pool lifecycle itself.
"""

import contextlib
from typing import Any
from urllib.parse import urlparse

from arq.connections import RedisSettings

from app.core.config import environment, logger

_arq_pool: Any = None


def build_arq_redis_settings(url: str) -> RedisSettings:
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or "0"),
        password=parsed.password,
    )


async def get_arq_pool() -> Any:
    """Get or create the shared arq Redis job-queue pool."""
    global _arq_pool
    if _arq_pool is None:
        from arq import create_pool

        settings = build_arq_redis_settings(environment.REDIS_URL)
        _arq_pool = await create_pool(settings)
        logger.info("arq pool connected")
    return _arq_pool


async def close_arq_pool() -> None:
    """Close the arq pool gracefully on app shutdown."""
    global _arq_pool
    if _arq_pool is not None:
        with contextlib.suppress(Exception):
            await _arq_pool.close()
        _arq_pool = None
        logger.info("arq pool closed")
