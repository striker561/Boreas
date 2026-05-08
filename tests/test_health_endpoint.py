import os
import json
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("APP_NAME", "Boreas")
os.environ.setdefault("APP_VERSION", "1.0.0")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("TRUSTED_HOSTS", "localhost")
os.environ.setdefault("STORAGE_ACCESS_KEY_ID", "key")
os.environ.setdefault("STORAGE_SECRET_ACCESS_KEY", "secret")
os.environ.setdefault("STORAGE_BUCKET_NAME", "bucket")


class HealthEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_endpoint_reports_queue_metrics(self) -> None:
        fake_redis = AsyncMock()
        fake_redis.ping.return_value = True

        fake_storage = AsyncMock()
        fake_storage.queue_depth.side_effect = [3, 1]
        fake_storage.staged_upload_count.return_value = 2

        with patch("app.main.get_redis_cache", return_value=fake_redis), patch(
            "app.main.get_arq_pool", new=AsyncMock(return_value=object())
        ), patch("app.main.build_media_storage_service", return_value=fake_storage):
            from app.main import public_health

            response = await public_health()

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body)["data"]
        self.assertEqual(payload["queue_depths"]["boreas:media"], 3)
        self.assertEqual(payload["queue_depths"]["boreas:compute"], 1)
        self.assertEqual(payload["staged_uploads"], 2)
        self.assertEqual(payload["limits"]["result_url_ttl_seconds"], 3600)
