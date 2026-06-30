import os
import unittest
from unittest.mock import AsyncMock

os.environ.setdefault("APP_NAME", "Boreas")
os.environ.setdefault("APP_VERSION", "1.0.0")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("TRUSTED_HOSTS", "localhost")
os.environ.setdefault("STORAGE_ACCESS_KEY_ID", "key")
os.environ.setdefault("STORAGE_SECRET_ACCESS_KEY", "secret")
os.environ.setdefault("STORAGE_BUCKET_NAME", "bucket")

from app.core.storage.media import JobStatus, MediaJob, MediaStorageService
from app.features.media.streams.hub import JobNotifyHub, job_id_from_notify_channel


class SaveJobNotifyTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_job_publishes_notify_channel(self) -> None:
        redis_cache = AsyncMock()
        redis_cache.set_json = AsyncMock(return_value=True)
        redis_cache.publish = AsyncMock(return_value=1)
        storage = MediaStorageService(
            redis_cache=redis_cache,
            object_storage=AsyncMock(),
            job_ttl_seconds=3600,
            result_url_ttl_seconds=3600,
            staged_upload_ttl_seconds=900,
        )
        job = MediaJob(
            job_id="job-1",
            status=JobStatus.queued,
            source_key="jobs/media/source/job-1",
            result_key="jobs/media/result/job-1.png",
            source_content_type="image/png",
        )

        await storage.save_job(job)

        redis_cache.publish.assert_awaited_once_with("jobs:media:job-1:notify")


class JobNotifyHubTests(unittest.IsolatedAsyncioTestCase):
    def test_job_id_from_notify_channel(self) -> None:
        self.assertEqual(
            job_id_from_notify_channel("jobs:media:abc-123:notify"),
            "abc-123",
        )
        self.assertIsNone(job_id_from_notify_channel("jobs:media:bad"))

    async def test_wake_only_matching_job_waiters(self) -> None:
        hub = JobNotifyHub()
        job_a = hub.subscribe("job-a")
        job_b = hub.subscribe("job-b")

        hub.wake("job-a")

        self.assertTrue(job_a.is_set())
        self.assertFalse(job_b.is_set())

    def test_stats_reports_stream_counts(self) -> None:
        hub = JobNotifyHub()
        hub.subscribe("job-a")
        hub.subscribe("job-a")
        hub.subscribe("job-b")

        stats = hub.stats()

        self.assertEqual(stats["active_streams"], 3)
        self.assertEqual(stats["tracked_jobs"], 2)
        self.assertFalse(stats["listener_running"])


if __name__ == "__main__":
    unittest.main()
