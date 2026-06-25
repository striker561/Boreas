from functools import lru_cache

from app.core.config import environment, logger
from app.core.queue import QueueName, get_arq_pool
from app.core.storage import (
    MediaStorageService,
    RedisCache,
    build_media_storage_service,
    get_redis_cache,
)
from app.core.worker_heartbeats import (
    COMPUTE_HEARTBEAT_TTL,
    HEARTBEAT_SCAN_PATTERN,
    HEARTBEAT_TTL_BY_QUEUE,
    QUEUE_COMPUTE,
    QUEUE_MEDIA,
)
from app.features.health.schemas import (
    HealthDependencyStatus,
    HealthLimits,
    HealthReport,
    HealthStatusPayload,
    HealthWorkers,
    WorkerHeartbeat,
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

    async def get_status(self) -> HealthStatusPayload:
        return HealthStatusPayload()

    async def get_health(self) -> tuple[int, HealthReport]:
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

        worker_heartbeats, stale_workers = await self._check_worker_heartbeats()

        if stale_workers:
            arq_ok = False

        status = "ok" if redis_ok and arq_ok else "degraded"
        if status != "ok":
            logger.warning(
                "Health check degraded",
                redis_ok=redis_ok,
                arq_ok=arq_ok,
                stale_workers=stale_workers,
            )

        return (
            200 if status == "ok" else 503,
            HealthReport(
                status=status,
                redis=HealthDependencyStatus(reachable=redis_ok),
                arq=HealthDependencyStatus(reachable=arq_ok),
                queue_depths=queue_depths,
                staged_uploads=staged_uploads,
                workers=HealthWorkers(
                    media=environment.MEDIA_WORKERS,
                    background_removal=environment.BACKGROUND_REMOVAL_WORKERS,
                ),
                limits=HealthLimits(
                    api_rate_limit=environment.API_RATE_LIMIT,
                    upload_rate_limit=environment.UPLOAD_RATE_LIMIT,
                    job_ttl_seconds=environment.JOB_TTL_SECONDS,
                    result_url_ttl_seconds=environment.RESULT_URL_TTL_SECONDS,
                    media_source_max_bytes=environment.MEDIA_SOURCE_MAX_BYTES,
                ),
                worker_heartbeats=worker_heartbeats,
                stale_workers=stale_workers,
            ),
        )

    async def _check_arq(self) -> bool:
        try:
            return await get_arq_pool() is not None
        except Exception as exc:
            logger.warning("ARQ health check failed", error=type(exc).__name__)
            return False

    async def _check_worker_heartbeats(
        self,
    ) -> tuple[dict[str, WorkerHeartbeat], list[str]]:
        """Scan heartbeat keys and return per-worker status + stale worker list."""
        heartbeats: dict[str, WorkerHeartbeat] = {}
        stale: list[str] = []
        live_by_queue = {QUEUE_MEDIA: 0, QUEUE_COMPUTE: 0}

        try:
            raw = await self.redis_cache.scan_values(HEARTBEAT_SCAN_PATTERN)
        except Exception as exc:
            logger.warning("Worker heartbeat scan failed", error=type(exc).__name__)
            return heartbeats, stale

        for key, data in raw.items():
            if not isinstance(data, dict):
                continue
            pid = data.get("pid", 0)
            last_job_id = data.get("last_job_id", "")
            queue = data.get("queue", "")

            staleness = 0.0
            ttl = 0
            try:
                client = await self.redis_cache._get_client()
                ttl = await client.ttl(key)
            except Exception:
                pass

            heartbeat_ttl = HEARTBEAT_TTL_BY_QUEUE.get(queue, COMPUTE_HEARTBEAT_TTL)

            if ttl is None or ttl <= 0:
                stale.append(str(pid))
                staleness = float("inf")
            else:
                live_by_queue[queue] = live_by_queue.get(queue, 0) + 1
                staleness = max(0.0, float(heartbeat_ttl) - float(ttl))

            worker_key = str(pid)
            heartbeats[worker_key] = WorkerHeartbeat(
                pid=pid,
                queue=queue,
                last_job_id=last_job_id,
                staleness_seconds=staleness,
            )

        expected_by_queue = {
            QUEUE_MEDIA: environment.MEDIA_WORKERS,
            QUEUE_COMPUTE: environment.BACKGROUND_REMOVAL_WORKERS,
        }
        for queue, expected in expected_by_queue.items():
            live = live_by_queue.get(queue, 0)
            if live < expected:
                stale.append(f"missing:{queue}:{expected - live}")

        return heartbeats, stale


@lru_cache(maxsize=1)
def build_health_service() -> HealthService:
    return HealthService(
        redis_cache=get_redis_cache(),
        storage=build_media_storage_service(),
    )
