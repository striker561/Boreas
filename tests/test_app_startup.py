import importlib
import os
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

app_module = importlib.import_module("app.core.app")


class _FlakyRedisCache:
    def __init__(self, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.attempts = 0

    async def connect(self) -> None:
        self.attempts += 1
        if self.attempts <= self.failures_before_success:
            raise ConnectionError("Temporary failure in name resolution")


class StartupDependencyWarmupTests(unittest.IsolatedAsyncioTestCase):
    async def test_warm_startup_dependencies_retries_until_success(self) -> None:
        redis_cache = _FlakyRedisCache(failures_before_success=2)
        get_arq_pool = AsyncMock(return_value=object())
        sleep = AsyncMock()

        with patch.object(app_module, "get_arq_pool", get_arq_pool), patch.object(
            app_module.asyncio,
            "sleep",
            sleep,
        ):
            await app_module._warm_startup_dependencies(redis_cache)

        self.assertEqual(redis_cache.attempts, 3)
        get_arq_pool.assert_awaited_once()
        self.assertEqual(sleep.await_count, 2)

    async def test_warm_startup_dependencies_raises_after_final_attempt(self) -> None:
        redis_cache = _FlakyRedisCache(
            failures_before_success=app_module.STARTUP_DEPENDENCY_MAX_ATTEMPTS
        )
        get_arq_pool = AsyncMock(return_value=object())
        sleep = AsyncMock()

        with patch.object(app_module, "get_arq_pool", get_arq_pool), patch.object(
            app_module.asyncio,
            "sleep",
            sleep,
        ):
            with self.assertRaises(ConnectionError):
                await app_module._warm_startup_dependencies(redis_cache)

        self.assertEqual(
            redis_cache.attempts,
            app_module.STARTUP_DEPENDENCY_MAX_ATTEMPTS,
        )
        self.assertEqual(
            sleep.await_count,
            app_module.STARTUP_DEPENDENCY_MAX_ATTEMPTS - 1,
        )
