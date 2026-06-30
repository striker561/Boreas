from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.storage import MediaStorageService, RedisCache, TERMINAL_JOB_STATUSES


SOURCE_PREFIX = "jobs/media/source/"
RESULT_PREFIX = "jobs/media/result/"

# ponytail: cleanup-only scan scope; MediaStorageService stays per-job keyed ops
_MEDIA_JOB_SCAN_PATTERN = "jobs:media:*"
_STAGED_UPLOAD_KEY_MARKER = ":staged-upload:"
_MEDIA_JOB_KEY_PREFIX = "jobs:media:"


@dataclass(frozen=True)
class CleanupSummary:
    redis_jobs_deleted: int
    s3_objects_deleted: int


class TasksCleanupService:
    def __init__(
        self,
        storage: MediaStorageService,
        redis_cache: RedisCache,
    ) -> None:
        self.storage = storage
        self.redis_cache = redis_cache

    async def run_hourly_cleanup(self) -> CleanupSummary:
        redis_deleted, job_s3_deleted = await self._cleanup_redis_jobs()
        s3_deleted = job_s3_deleted + await self._cleanup_s3_objects()
        return CleanupSummary(
            redis_jobs_deleted=redis_deleted,
            s3_objects_deleted=s3_deleted,
        )

    async def _iter_job_ids_for_cleanup(self) -> list[str]:
        job_ids: list[str] = []
        for key in await self.redis_cache.scan_keys(_MEDIA_JOB_SCAN_PATTERN):
            if _STAGED_UPLOAD_KEY_MARKER in key:
                continue
            if not key.startswith(_MEDIA_JOB_KEY_PREFIX):
                continue
            job_ids.append(key.removeprefix(_MEDIA_JOB_KEY_PREFIX))
        return job_ids

    async def _cleanup_redis_jobs(self) -> tuple[int, int]:
        cutoff = datetime.now(UTC) - timedelta(seconds=self.storage.job_ttl_seconds)
        deleted = 0
        s3_deleted = 0
        for job_id in await self._iter_job_ids_for_cleanup():
            job = await self.storage.get_job(job_id)
            if job is None:
                continue
            updated_at = job.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
            if job.status in TERMINAL_JOB_STATUSES or updated_at <= cutoff:
                await self.storage.delete_staged_upload(job_id)
                s3_deleted += await self.storage.delete_job_objects(job)
                await self.storage.delete_job(job_id)
                deleted += 1
        return deleted, s3_deleted

    async def _cleanup_s3_objects(self) -> int:
        deleted = 0
        for prefix in (SOURCE_PREFIX, RESULT_PREFIX):
            deleted += await self.storage.object_storage.delete_objects_older_than(
                prefix,
                self.storage.job_ttl_seconds,
            )
        return deleted
