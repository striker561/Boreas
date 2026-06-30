import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("APP_NAME", "Boreas")
os.environ.setdefault("APP_VERSION", "1.0.0")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("TRUSTED_HOSTS", "localhost")
os.environ.setdefault("STORAGE_ACCESS_KEY_ID", "key")
os.environ.setdefault("STORAGE_SECRET_ACCESS_KEY", "secret")
os.environ.setdefault("STORAGE_BUCKET_NAME", "bucket")

from app.core.storage.media import JobStatus, MediaJob, MediaStorageService
from app.features.tasks.service import SOURCE_PREFIX, TasksCleanupService


def _job(
    job_id: str,
    *,
    status: JobStatus = JobStatus.complete,
    updated_at: datetime | None = None,
) -> MediaJob:
    return MediaJob(
        job_id=job_id,
        status=status,
        source_key=f"jobs/media/source/{job_id}",
        result_key=f"jobs/media/result/{job_id}.png",
        source_content_type="image/png",
        updated_at=updated_at or datetime.now(UTC),
    )


class TasksCleanupTests(unittest.IsolatedAsyncioTestCase):
    def _build_service(self) -> tuple[TasksCleanupService, MagicMock, AsyncMock]:
        storage = MagicMock(spec=MediaStorageService)
        storage.job_ttl_seconds = 3600
        storage.get_job = AsyncMock(return_value=None)
        storage.delete_job = AsyncMock()
        storage.delete_staged_upload = AsyncMock()
        storage.delete_job_objects = AsyncMock(return_value=2)
        storage.object_storage = MagicMock()
        storage.object_storage.delete_objects_older_than = AsyncMock(return_value=0)
        redis_cache = AsyncMock()
        redis_cache.scan_keys = AsyncMock(return_value=[])
        return (
            TasksCleanupService(storage=storage, redis_cache=redis_cache),
            storage,
            redis_cache,
        )

    async def test_deletes_terminal_jobs(self) -> None:
        service, storage, redis_cache = self._build_service()
        redis_cache.scan_keys.return_value = ["jobs:media:done-job"]
        storage.get_job.return_value = _job("done-job", status=JobStatus.complete)

        summary = await service.run_hourly_cleanup()

        storage.delete_staged_upload.assert_awaited_once_with("done-job")
        storage.delete_job_objects.assert_awaited_once()
        storage.delete_job.assert_awaited_once_with("done-job")
        self.assertEqual(summary.redis_jobs_deleted, 1)
        self.assertEqual(summary.s3_objects_deleted, 2)

    async def test_skips_staged_upload_keys(self) -> None:
        service, storage, redis_cache = self._build_service()
        redis_cache.scan_keys.return_value = [
            "jobs:media:staged-upload:orphan:meta",
            "jobs:media:done-job",
        ]
        storage.get_job.return_value = _job("done-job", status=JobStatus.complete)

        summary = await service.run_hourly_cleanup()

        storage.get_job.assert_awaited_once_with("done-job")
        self.assertEqual(summary.redis_jobs_deleted, 1)

    async def test_deletes_stale_non_terminal_jobs(self) -> None:
        service, storage, redis_cache = self._build_service()
        stale_at = datetime.now(UTC) - timedelta(hours=2)
        redis_cache.scan_keys.return_value = ["jobs:media:stuck-job"]
        storage.get_job.return_value = _job(
            "stuck-job",
            status=JobStatus.processing,
            updated_at=stale_at,
        )

        summary = await service.run_hourly_cleanup()

        storage.delete_job.assert_awaited_once_with("stuck-job")
        self.assertEqual(summary.redis_jobs_deleted, 1)

    async def test_keeps_active_non_terminal_jobs(self) -> None:
        service, storage, redis_cache = self._build_service()
        redis_cache.scan_keys.return_value = ["jobs:media:active-job"]
        storage.get_job.return_value = _job(
            "active-job",
            status=JobStatus.processing,
            updated_at=datetime.now(UTC),
        )

        summary = await service.run_hourly_cleanup()

        storage.delete_job.assert_not_awaited()
        self.assertEqual(summary.redis_jobs_deleted, 0)

    async def test_s3_sweep_uses_job_ttl_and_prefixes(self) -> None:
        service, storage, _redis_cache = self._build_service()
        storage.object_storage.delete_objects_older_than.side_effect = [2, 2]

        summary = await service.run_hourly_cleanup()

        storage.object_storage.delete_objects_older_than.assert_any_await(
            SOURCE_PREFIX,
            3600,
        )
        storage.object_storage.delete_objects_older_than.assert_any_await(
            "jobs/media/result/",
            3600,
        )
        self.assertEqual(summary.s3_objects_deleted, 4)
