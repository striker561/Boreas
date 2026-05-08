from fastapi import Depends

from app.features.rembg.service import RembgProcessor
from app.features.storage import (
    RembgStorageService,
    build_rembg_storage_service,
    get_rembg_storage_service,
)


def build_rembg_processor() -> RembgProcessor:
    return RembgProcessor(storage=build_rembg_storage_service())


async def get_rembg_processor(
    storage: RembgStorageService = Depends(get_rembg_storage_service),
) -> RembgProcessor:
    return RembgProcessor(storage=storage)
