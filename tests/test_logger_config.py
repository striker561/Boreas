import importlib
import logging
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("APP_NAME", "Boreas")
os.environ.setdefault("APP_VERSION", "1.0.0")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("TRUSTED_HOSTS", "localhost")
os.environ.setdefault("STORAGE_ACCESS_KEY_ID", "key")
os.environ.setdefault("STORAGE_SECRET_ACCESS_KEY", "secret")
os.environ.setdefault("STORAGE_BUCKET_NAME", "bucket")

logger_module = importlib.import_module("app.core.config.logger")


class AxiomHandlerSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        logger_module._build_stdlib_logger.cache_clear()

    def tearDown(self) -> None:
        # Remove the logger so other tests get a clean state.
        logging.Logger.manager.loggerDict.pop("Boreas", None)
        logging.Logger.manager.loggerDict.pop("boreas-test", None)
        logger_module._build_stdlib_logger.cache_clear()

    def test_no_axiom_handler_when_token_absent(self) -> None:
        settings = SimpleNamespace(
            APP_NAME="Boreas",
            LOG_LEVEL="INFO",
            AXIOM_TOKEN=None,
            AXIOM_DATASET="boreas-logs",
        )

        with patch.object(logger_module, "get_environment", return_value=settings):
            built_logger = logger_module._build_stdlib_logger()

        handler_types = [type(h).__name__ for h in built_logger.handlers]
        self.assertNotIn("AxiomHandler", handler_types)
        self.assertEqual(len(built_logger.handlers), 1)

    def test_axiom_handler_added_when_token_present(self) -> None:
        settings = SimpleNamespace(
            APP_NAME="boreas-test",
            LOG_LEVEL="INFO",
            AXIOM_TOKEN="xaat-test-token",
            AXIOM_DATASET="boreas-logs",
        )

        mock_handler = MagicMock(spec=logging.Handler)
        mock_handler.level = logging.INFO
        mock_client = MagicMock()

        with patch.object(
            logger_module, "get_environment", return_value=settings
        ), patch.dict(
            "sys.modules",
            {
                "axiom_py": MagicMock(Client=MagicMock(return_value=mock_client)),
                "axiom_py.logging": MagicMock(
                    AxiomHandler=MagicMock(return_value=mock_handler)
                ),
            },
        ):
            built_logger = logger_module._build_stdlib_logger()

        self.assertIn(mock_handler, built_logger.handlers)
