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


if __name__ == "__main__":
    unittest.main()
