"""S3-compatible storage backend backed by aioboto3."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError

class S3Backend:
    """Async S3-compatible storage backend."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None,
        access_key: str,
        secret_key: str,
        region: str = "auto",
    ) -> None:
        self._bucket = bucket
        self._endpoint_url = endpoint_url
        self._session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        # Disable checksum validation — R2 does not support all AWS checksum
        # algorithms, and letting boto3 auto-add them causes 400 errors.
        self._client_config = Config(
            signature_version="s3v4",
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        )

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[Any]:
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            config=self._client_config,
        ) as client:
            yield client

    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> None:
        """Upload a full object from memory."""
        params: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": data,
        }
        if content_type is not None:
            params["ContentType"] = content_type

        async with self._client() as s3:
            await s3.put_object(**params)

    async def download_bytes(self, key: str) -> bytes:
        """Download a full object into memory."""
        async with self._client() as s3:
            response = await s3.get_object(Bucket=self._bucket, Key=key)
            async with response["Body"] as stream:
                return await stream.read()  # type: ignore[no-any-return]

    async def presign_read(self, key: str, expires_in: int = 3600) -> str:
        """Generate a time-limited GET URL for a private object."""
        async with self._client() as s3:
            url: str = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        return url

    async def delete(self, key: str) -> None:
        """Delete a single object."""
        async with self._client() as s3:
            await s3.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        """Check whether an object exists."""
        async with self._client() as s3:
            try:
                await s3.head_object(Bucket=self._bucket, Key=key)
                return True
            except ClientError as exc:
                if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                    return False
                raise
