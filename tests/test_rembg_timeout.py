import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("APP_NAME", "Boreas")
os.environ.setdefault("APP_VERSION", "1.0.0")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("TRUSTED_HOSTS", "localhost")
os.environ.setdefault("STORAGE_ACCESS_KEY_ID", "key")
os.environ.setdefault("STORAGE_SECRET_ACCESS_KEY", "secret")
os.environ.setdefault("STORAGE_BUCKET_NAME", "bucket")

from app.lib.rembg import service as rembg_service_module


class RembgTimeoutTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        rembg_service_module.get_rembg_executor.cache_clear()

    async def test_remove_background_image_raises_rembg_timeout_error(self) -> None:
        with patch(
            "app.lib.rembg.service.asyncio.wait_for",
            side_effect=asyncio.TimeoutError,
        ):
            with self.assertRaises(rembg_service_module.RembgTimeoutError):
                await rembg_service_module.remove_background_image(b"source")

    def test_shutdown_rembg_executor_clears_cache(self) -> None:
        executor = rembg_service_module.get_rembg_executor()
        rembg_service_module.shutdown_rembg_executor()
        new_executor = rembg_service_module.get_rembg_executor()
        self.assertIsNot(executor, new_executor)

    def test_inference_timeout_reads_environment(self) -> None:
        with patch.object(
            rembg_service_module,
            "get_environment",
            return_value=SimpleNamespace(REMBG_INFERENCE_TIMEOUT_SECONDS=90),
        ):
            self.assertEqual(rembg_service_module._inference_timeout_seconds(), 90)
