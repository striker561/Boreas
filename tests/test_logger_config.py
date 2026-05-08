import importlib
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

logger_module = importlib.import_module("app.core.config.logger")


class LogfireConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        logger_module._get_logfire_client.cache_clear()

    def tearDown(self) -> None:
        logger_module._get_logfire_client.cache_clear()

    def test_get_logfire_client_disables_duplicate_console_output(self) -> None:
        settings = SimpleNamespace(
            APP_VERSION="1.0.0",
            IS_PRODUCTION=False,
            LOG_LEVEL="INFO",
            LOGFIRE_ENVIRONMENT=None,
            LOGFIRE_SEND_TO_LOGFIRE=True,
            LOGFIRE_SERVICE_NAME="boreas",
            LOGFIRE_TOKEN="token",
        )

        with patch.object(
            logger_module,
            "get_environment",
            return_value=settings,
        ), patch.object(
            logger_module.logfire,
            "configure",
            return_value=object(),
        ) as configure_mock:
            logger_module._get_logfire_client()

        configure_kwargs = configure_mock.call_args.kwargs
        self.assertNotIn("local", configure_kwargs)
        self.assertFalse(configure_kwargs["console"])
        self.assertNotIn("environment", configure_kwargs)

    def test_get_logfire_client_only_sets_environment_when_configured(self) -> None:
        settings = SimpleNamespace(
            APP_VERSION="1.0.0",
            IS_PRODUCTION=True,
            LOG_LEVEL="INFO",
            LOGFIRE_ENVIRONMENT="production",
            LOGFIRE_SEND_TO_LOGFIRE=True,
            LOGFIRE_SERVICE_NAME="boreas",
            LOGFIRE_TOKEN="token",
        )

        with patch.object(
            logger_module,
            "get_environment",
            return_value=settings,
        ), patch.object(
            logger_module.logfire,
            "configure",
            return_value=object(),
        ) as configure_mock:
            logger_module._get_logfire_client()

        self.assertEqual(
            configure_mock.call_args.kwargs["environment"],
            "production",
        )
