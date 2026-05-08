from typing import Any

from fastapi import Depends

from app.core.queue import get_arq_pool
from app.features.client.service import ClientService
from app.features.storage import build_rembg_storage_service


def build_client_service(queue_pool: Any) -> ClientService:
    return ClientService(
        storage=build_rembg_storage_service(),
        queue_pool=queue_pool,
    )


async def get_client_service(
    queue_pool: Any = Depends(get_arq_pool),
) -> ClientService:
    return build_client_service(queue_pool=queue_pool)
