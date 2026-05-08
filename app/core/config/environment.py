from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_NAME: str
    APP_VERSION: str
    IS_PRODUCTION: bool = False

    REDIS_URL: str

    CORS_ORIGINS: str
    TRUSTED_HOSTS: str
    MAX_BODY_SIZE: int = 10 * 1024 * 1024
    GZIP_MIN_SIZE: int = 1024

    BG_WORKERS: int = 2
    MEDIA_WORKERS: int = 1

    STORAGE_ENDPOINT_URL: str = ""
    STORAGE_ACCESS_KEY_ID: str
    STORAGE_SECRET_ACCESS_KEY: str
    STORAGE_BUCKET_NAME: str
    STORAGE_REGION: str = "auto"
    STORAGE_TTL_HOURS: int = 1

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]

    @property
    def trusted_hosts_list(self) -> list[str]:
        """Parse trusted hosts from comma-separated string."""
        return [host.strip() for host in self.TRUSTED_HOSTS.split(",") if host.strip()]


@lru_cache
def get_environment() -> Environment:
    """Return the cached settings object."""
    return Environment()
