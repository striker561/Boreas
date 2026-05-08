import unittest
from unittest.mock import AsyncMock, patch

from botocore.exceptions import ClientError

from app.lib.storage.s3 import S3Backend


class _AsyncClientContext:
    def __init__(self, client) -> None:
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class S3BackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_exists_treats_r2_bad_request_as_missing(self) -> None:
        backend = S3Backend(
            bucket="bucket",
            endpoint_url="https://example.r2.cloudflarestorage.com",
            access_key="key",
            secret_key="secret",
        )
        client = AsyncMock()
        client.head_object.side_effect = ClientError(
            {
                "Error": {"Code": "400", "Message": "Bad Request"},
                "ResponseMetadata": {"HTTPStatusCode": 400},
            },
            "HeadObject",
        )

        with patch.object(backend, "_client", return_value=_AsyncClientContext(client)):
            exists = await backend.exists("jobs/media/result/missing.png")

        self.assertFalse(exists)
