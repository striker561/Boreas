from functools import lru_cache

from fastapi import Depends

from app.core.storage import (
    MediaStorageService,
    build_media_storage_service,
    get_media_storage_service,
)
from app.features.rembg.service import BackgroundRemovalProcessor


@lru_cache(maxsize=1)
def build_background_removal_processor() -> BackgroundRemovalProcessor:
    return BackgroundRemovalProcessor(storage=build_media_storage_service())


async def get_background_removal_processor(
    storage: MediaStorageService = Depends(get_media_storage_service),
) -> BackgroundRemovalProcessor:
    return BackgroundRemovalProcessor(storage=storage)
