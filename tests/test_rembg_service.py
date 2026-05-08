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


class RembgServiceTests(unittest.TestCase):
    def tearDown(self) -> None:
        rembg_service_module.get_rembg_session.cache_clear()
        rembg_service_module.get_rembg_remove_options.cache_clear()

    def test_remove_background_uses_quality_and_hardening_options(self) -> None:
        environment = SimpleNamespace(
            REMBG_MODEL="isnet-general-use",
            REMBG_ALPHA_MATTING=True,
            REMBG_ALPHA_MATTING_FOREGROUND_THRESHOLD=245,
            REMBG_ALPHA_MATTING_BACKGROUND_THRESHOLD=15,
            REMBG_ALPHA_MATTING_ERODE_SIZE=6,
            REMBG_POST_PROCESS_MASK=True,
        )

        with patch.object(
            rembg_service_module,
            "get_environment",
            return_value=environment,
        ), patch.object(
            rembg_service_module,
            "new_session",
            return_value="session",
        ) as new_session_mock, patch.object(
            rembg_service_module,
            "remove",
            return_value=b"cutout-bytes",
        ) as remove_mock:
            result = rembg_service_module._remove_background(b"source-bytes")

        self.assertEqual(result, b"cutout-bytes")
        new_session_mock.assert_called_once_with("isnet-general-use")
        remove_mock.assert_called_once_with(
            b"source-bytes",
            session="session",
            alpha_matting=True,
            alpha_matting_foreground_threshold=245,
            alpha_matting_background_threshold=15,
            alpha_matting_erode_size=6,
            post_process_mask=True,
            force_return_bytes=True,
        )

    def test_remove_background_rejects_non_bytes_results(self) -> None:
        environment = SimpleNamespace(
            REMBG_MODEL="isnet-general-use",
            REMBG_ALPHA_MATTING=False,
            REMBG_ALPHA_MATTING_FOREGROUND_THRESHOLD=240,
            REMBG_ALPHA_MATTING_BACKGROUND_THRESHOLD=10,
            REMBG_ALPHA_MATTING_ERODE_SIZE=10,
            REMBG_POST_PROCESS_MASK=True,
        )

        with patch.object(
            rembg_service_module,
            "get_environment",
            return_value=environment,
        ), patch.object(
            rembg_service_module,
            "new_session",
            return_value="session",
        ), patch.object(
            rembg_service_module,
            "remove",
            return_value="not-bytes",
        ):
            with self.assertRaises(TypeError):
                rembg_service_module._remove_background(b"source-bytes")