from typing import Any

from fastapi import Depends

from app.core.queue import get_arq_pool
from app.features.client.service import RembgClientService
from app.features.storage import build_rembg_storage_service


def build_rembg_client_service(queue_pool: Any) -> RembgClientService:
    return RembgClientService(
        storage=build_rembg_storage_service(),
        queue_pool=queue_pool,
    )


async def get_rembg_client_service(
    queue_pool: Any = Depends(get_arq_pool),
) -> RembgClientService:
    return build_rembg_client_service(queue_pool=queue_pool)
