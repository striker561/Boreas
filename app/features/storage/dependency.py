from app.core.config import environment
from app.core.storage.dependency import get_redis_cache
from app.features.storage.dal import StorageDAL
from app.features.storage.service import MediaStorageService
from app.lib.storage import get_storage


def build_media_storage_service() -> MediaStorageService:
    dal = StorageDAL(
        redis_cache=get_redis_cache(),
        object_storage=get_storage(),
        ttl_seconds=environment.STORAGE_TTL_HOURS * 60 * 60,
    )
    return MediaStorageService(dal=dal)


async def get_media_storage_service() -> MediaStorageService:
    return build_media_storage_service()
