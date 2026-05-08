import pickle
from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.core.config import logger


class RedisCache:
    """Async Redis cache with connection pooling."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: Redis | None = None
        self.pool: ConnectionPool | None = None

    async def connect(self) -> None:
        """Establish Redis connection pool."""
        if self.redis:
            try:
                if await self.redis.ping():
                    return  # Already connected
            except Exception as e:
                logger.debug("Redis ping failed, reconnecting", error=type(e).__name__)

        try:
            if self.redis:
                await self.redis.close()
            if self.pool:
                await self.pool.disconnect(inuse_connections=True)

            self.pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=20,
                decode_responses=False,
            )
            self.redis = Redis(connection_pool=self.pool)
            await self.redis.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.error("Redis connection failed", error=str(e))
            self.redis = None
            self.pool = None
            raise

    async def disconnect(self) -> None:
        """Close Redis connection and pool."""
        if self.redis:
            try:
                await self.redis.close()
            except Exception as e:
                logger.warning("Redis close error", error=str(e))

        if self.pool:
            try:
                await self.pool.disconnect(inuse_connections=True)
            except Exception as e:
                logger.warning("Redis pool disconnect error", error=str(e))

        self.redis = None
        self.pool = None
        logger.info("Redis disconnected")

    async def ping(self) -> bool:
        """Check Redis connectivity. Returns True if reachable, False otherwise."""
        try:
            client = await self._get_client()
            return await client.ping() is True
        except Exception:
            return False

    async def _get_client(self) -> Redis:
        """Get Redis client, reconnect if needed."""
        if not self.redis:
            await self.connect()

        if not self.redis:
            raise ConnectionError("Redis not available")

        try:
            await self.redis.ping()
        except Exception:
            await self.connect()

        if not self.redis:
            raise ConnectionError("Redis not available")

        return self.redis

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache. Returns pickled data or default."""
        try:
            client = await self._get_client()
            value = await client.get(key)

            if value is None:
                return default

            return pickle.loads(value)  # noqa: S301
        except Exception as e:
            logger.error("Redis get failed", key=key, error=type(e).__name__)
            return default

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in cache with optional TTL (seconds)."""
        try:
            client = await self._get_client()
            data = pickle.dumps(value)
            result = await client.set(key, data, ex=ttl)
            return result is True
        except Exception as e:
            logger.error("Redis set failed", key=key, error=type(e).__name__)
            return False

    async def delete(self, *keys: str) -> int:
        """Delete keys from cache. Returns count of deleted keys."""
        if not keys:
            return 0

        try:
            client = await self._get_client()
            return await client.delete(*keys) or 0
        except Exception as e:
            logger.error("Redis delete failed", keys=keys, error=type(e).__name__)
            return 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            client = await self._get_client()
            return await client.exists(key) > 0
        except Exception:
            return False

    async def incr(self, key: str, expire_if_new: int | None = None) -> int:
        """
        Atomically increment an integer counter stored at *key*.

        If *expire_if_new* is provided and the counter is brand-new (count == 1),
        sets a TTL of that many seconds.  This gives a sliding-window counter
        without a separate EXPIRE call on every request.

        Raises on Redis errors so the caller can decide whether to fail open/closed.
        """
        client = await self._get_client()
        count: int = await client.incr(key)
        if expire_if_new is not None and count == 1:
            await client.expire(key, expire_if_new)
        return count
