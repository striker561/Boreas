"""Configured object-storage dependency."""

from functools import lru_cache

from app.core.config import environment
from app.lib.storage.backend import StorageBackend
from app.lib.storage.s3 import S3Backend


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    """Return the shared storage backend instance."""
    return S3Backend(
        bucket=environment.STORAGE_BUCKET_NAME,
        endpoint_url=environment.STORAGE_ENDPOINT_URL or None,
        access_key=environment.STORAGE_ACCESS_KEY_ID,
        secret_key=environment.STORAGE_SECRET_ACCESS_KEY,
        region=environment.STORAGE_REGION,
    )
