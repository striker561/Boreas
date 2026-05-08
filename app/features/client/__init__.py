from app.features.client.dependency import (
    build_client_service,
    get_client_service,
)
from app.features.client.routes import router
from app.features.client.service import ClientService

__all__ = [
    "ClientService",
    "build_client_service",
    "get_client_service",
    "router",
]
