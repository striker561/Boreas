import os
import unittest
from unittest.mock import patch

os.environ.setdefault("APP_NAME", "Boreas")
os.environ.setdefault("APP_VERSION", "1.0.0")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("TRUSTED_HOSTS", "localhost")
os.environ.setdefault("STORAGE_ACCESS_KEY_ID", "key")
os.environ.setdefault("STORAGE_SECRET_ACCESS_KEY", "secret")
os.environ.setdefault("STORAGE_BUCKET_NAME", "bucket")

from app.core import watchdog


class WatchdogConfigTests(unittest.TestCase):
    def test_worker_definitions_use_environment_settings(self) -> None:
        with patch.object(watchdog.environment, "MEDIA_WORKERS", 2), patch.object(
            watchdog.environment,
            "BACKGROUND_REMOVAL_WORKERS",
            3,
        ):
            definitions = watchdog._worker_definitions()

        self.assertEqual(definitions[0]["worker_count"], 2)
        self.assertEqual(definitions[1]["worker_count"], 3)
        self.assertEqual(
            definitions[0]["settings_class"],
            "app.core.queue.registry.MediaWorkerSettings",
        )
        self.assertEqual(
            definitions[1]["settings_class"],
            "app.core.queue.registry.BackgroundRemovalWorkerSettings",
        )
