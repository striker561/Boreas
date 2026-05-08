from app.features.client.dependency import (
    build_rembg_client_service,
    get_rembg_client_service,
)
from app.features.client.routes import router
from app.features.client.service import RembgClientService

__all__ = [
    "RembgClientService",
    "build_rembg_client_service",
    "get_rembg_client_service",
    "router",
]
