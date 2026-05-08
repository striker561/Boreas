from fastapi import APIRouter

from app.features.client import router as client_router

# Main API router with /api/v1 prefix
feature_router = APIRouter(prefix="/v1")

# Register all feature routers
feature_router.include_router(
    client_router,
    tags=["Rem BG"],
)
