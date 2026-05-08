import unittest

from app.core.config.environment import Environment


class EnvironmentConfigTests(unittest.TestCase):
    def test_trusted_hosts_list_always_includes_local_health_hosts(self) -> None:
        settings = Environment(
            APP_NAME="Boreas",
            APP_VERSION="1.0.0",
            REDIS_URL="redis://redis:6379/0",
            CORS_ORIGINS="http://localhost:3000",
            TRUSTED_HOSTS="boreas.kageapi.cloud",
            STORAGE_ACCESS_KEY_ID="key",
            STORAGE_SECRET_ACCESS_KEY="secret",
            STORAGE_BUCKET_NAME="bucket",
        )

        self.assertEqual(
            settings.trusted_hosts_list,
            ["boreas.kageapi.cloud", "localhost", "127.0.0.1", "::1"],
        )
