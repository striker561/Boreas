from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_INTERNAL_TRUSTED_HOSTS = ("localhost", "127.0.0.1", "::1")


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
    API_RATE_LIMIT: str = "5/minute"
    UPLOAD_RATE_LIMIT: str = "5/minute"
    LOG_LEVEL: str = "INFO"
    AXIOM_TOKEN: str | None = None
    AXIOM_DATASET: str = "boreas-logs"
    STARTUP_DEPENDENCY_MAX_ATTEMPTS: int = Field(default=10, ge=1, le=60)
    STARTUP_DEPENDENCY_RETRY_DELAY_SECONDS: float = Field(
        default=2.0,
        gt=0,
        le=30,
    )

    JOB_TTL_SECONDS: int = 60 * 60
    RESULT_URL_TTL_SECONDS: int = 60 * 60
    MEDIA_SOURCE_MAX_BYTES: int = 2 * 1024 * 1024
    MEDIA_STAGING_TTL_SECONDS: int = 15 * 60
    MEDIA_WORKERS: int = 1
    BACKGROUND_REMOVAL_WORKERS: int = 1

    STORAGE_ENDPOINT_URL: str = ""
    STORAGE_ACCESS_KEY_ID: str
    STORAGE_SECRET_ACCESS_KEY: str
    STORAGE_BUCKET_NAME: str
    STORAGE_REGION: str = "auto"

    REMBG_MODEL: str = "isnet-general-use"
    REMBG_POST_PROCESS_MASK: bool = True
    REMBG_ALPHA_MATTING: bool = False
    REMBG_ALPHA_MATTING_FOREGROUND_THRESHOLD: int = Field(
        default=240,
        ge=0,
        le=255,
    )
    REMBG_ALPHA_MATTING_BACKGROUND_THRESHOLD: int = Field(
        default=10,
        ge=0,
        le=255,
    )
    REMBG_ALPHA_MATTING_ERODE_SIZE: int = Field(
        default=10,
        ge=0,
        le=64,
    )
    REMBG_OMP_NUM_THREADS: int = Field(default=2, ge=1, le=16)

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
        configured_hosts = [
            host.strip() for host in self.TRUSTED_HOSTS.split(",") if host.strip()
        ]
        resolved_hosts: list[str] = []

        for host in [*configured_hosts, *_INTERNAL_TRUSTED_HOSTS]:
            if host not in resolved_hosts:
                resolved_hosts.append(host)

        return resolved_hosts


@lru_cache
def get_environment() -> Environment:
    """Return the cached settings object."""
    return Environment()  # type: ignore[call-arg]
