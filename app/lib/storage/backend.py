"""Object storage interface used by the API and workers."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Minimal storage contract for the current service."""

    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> None:
        """Upload raw bytes to the configured bucket."""
        ...

    async def download_bytes(self, key: str) -> bytes:
        """Read the full object into memory."""
        ...

    async def presign_read(self, key: str, expires_in: int = 3600) -> str:
        """Generate a time-limited read URL for a private object."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a single object."""
        ...

    async def exists(self, key: str) -> bool:
        """Return whether the object exists."""
        ...
