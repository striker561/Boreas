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

from app.features.rembg import workers as rembg_workers_module


class _FailingWarmProcessor:
    def warm_worker_dependencies(self) -> None:
        raise RuntimeError("download failed")


class RembgWorkerStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_warm_worker_does_not_fail_when_prewarm_errors(self) -> None:
        ctx: dict[str, object] = {}
        processor = _FailingWarmProcessor()

        with patch.object(
            rembg_workers_module,
            "build_background_removal_processor",
            return_value=processor,
        ):
            await rembg_workers_module.warm_background_removal_worker(ctx)

        self.assertIs(
            ctx[rembg_workers_module.BACKGROUND_REMOVAL_PROCESSOR_CONTEXT_KEY],
            processor,
        )
