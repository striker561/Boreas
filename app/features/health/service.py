from functools import lru_cache
from typing import Any

from app.core.config import environment, logger
from app.core.queue import QueueName, get_arq_pool
from app.core.storage import (
    MediaStorageService,
    RedisCache,
    build_media_storage_service,
    get_redis_cache,
)


class HealthService:
    def __init__(
        self,
        *,
        redis_cache: RedisCache,
        storage: MediaStorageService,
    ) -> None:
        self.redis_cache = redis_cache
        self.storage = storage

    async def get_status(self) -> dict[str, str]:
        return {"status": "ok"}

    async def get_health(self) -> tuple[int, dict[str, Any]]:
        redis_ok = await self.redis_cache.ping()
        arq_ok = await self._check_arq()

        queue_depths = {
            QueueName.media.value: await self.storage.queue_depth(
                QueueName.media.value
            ),
            QueueName.compute.value: await self.storage.queue_depth(
                QueueName.compute.value
            ),
        }
        staged_uploads = await self.storage.staged_upload_count()

        status = "ok" if redis_ok and arq_ok else "degraded"
        if status != "ok":
            logger.warning(
                "Health check degraded",
                redis_ok=redis_ok,
                arq_ok=arq_ok,
            )

        return (
            200 if status == "ok" else 503,
            {
                "status": status,
                "redis": {"reachable": redis_ok},
                "arq": {"reachable": arq_ok},
                "queue_depths": queue_depths,
                "staged_uploads": staged_uploads,
                "workers": {
                    "media": environment.MEDIA_WORKERS,
                    "background_removal": environment.BACKGROUND_REMOVAL_WORKERS,
                },
                "limits": {
                    "api_rate_limit": environment.API_RATE_LIMIT,
                    "upload_rate_limit": environment.UPLOAD_RATE_LIMIT,
                    "job_ttl_seconds": environment.JOB_TTL_SECONDS,
                    "result_url_ttl_seconds": environment.RESULT_URL_TTL_SECONDS,
                    "media_source_max_bytes": environment.MEDIA_SOURCE_MAX_BYTES,
                },
            },
        )

    async def _check_arq(self) -> bool:
        try:
            return await get_arq_pool() is not None
        except Exception as exc:
            logger.warning("ARQ health check failed", error=type(exc).__name__)
            return False


@lru_cache(maxsize=1)
def build_health_service() -> HealthService:
    return HealthService(
        redis_cache=get_redis_cache(),
        storage=build_media_storage_service(),
    )
