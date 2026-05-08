from typing import Any

from fastapi import Depends

from app.core.queue import get_arq_pool
from app.features.media.service import MediaService
from app.features.storage import MediaStorageService, build_media_storage_service


def build_media_service(
    queue_pool: Any,
    storage: MediaStorageService | None = None,
) -> MediaService:
    return MediaService(
        storage=storage or build_media_storage_service(),
        queue_pool=queue_pool,
    )


async def get_media_service(
    queue_pool: Any = Depends(get_arq_pool),
) -> MediaService:
    return build_media_service(
        queue_pool=queue_pool,
        storage=build_media_storage_service(),
    )
