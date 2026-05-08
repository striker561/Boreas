from app.core.storage.redis import RedisCache
from app.features.storage.schemas import RembgJob
from app.lib.storage import StorageBackend


class RembgStorageDAL:
    def __init__(
        self,
        redis_cache: RedisCache,
        object_storage: StorageBackend,
        ttl_seconds: int,
    ) -> None:
        self.redis_cache = redis_cache
        self.object_storage = object_storage
        self.ttl_seconds = ttl_seconds

    async def save_job(self, key: str, job: RembgJob) -> None:
        await self.redis_cache.set(
            key,
            job.model_dump(mode="json"),
            ttl=self.ttl_seconds,
        )

    async def get_job(self, key: str) -> RembgJob | None:
        payload = await self.redis_cache.get(key)
        if payload is None:
            return None
        return RembgJob.model_validate(payload)

    async def delete_job(self, key: str) -> None:
        await self.redis_cache.delete(key)

    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str,
    ) -> None:
        await self.object_storage.upload_bytes(key, data, content_type=content_type)

    async def download_bytes(self, key: str) -> bytes:
        return await self.object_storage.download_bytes(key)

    async def delete_object(self, key: str) -> None:
        await self.object_storage.delete(key)

    async def object_exists(self, key: str) -> bool:
        return await self.object_storage.exists(key)

    async def get_read_url(self, key: str) -> str:
        return await self.object_storage.presign_read(key, expires_in=self.ttl_seconds)
