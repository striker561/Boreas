from app.core.config import environment
from app.core.storage.dependency import get_redis_cache
from app.features.storage.dal import RembgStorageDAL
from app.features.storage.service import RembgStorageService
from app.lib.storage import get_storage


def build_rembg_storage_service() -> RembgStorageService:
    dal = RembgStorageDAL(
        redis_cache=get_redis_cache(),
        object_storage=get_storage(),
        ttl_seconds=environment.STORAGE_TTL_HOURS * 60 * 60,
    )
    return RembgStorageService(dal=dal)


async def get_rembg_storage_service() -> RembgStorageService:
    return build_rembg_storage_service()
