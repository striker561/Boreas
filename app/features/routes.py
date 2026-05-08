from fastapi import APIRouter

from app.features.health import router as health_router
from app.features.media import router as media_router

feature_router = APIRouter()
api_v1_router = APIRouter(prefix="/v1")

api_v1_router.include_router(media_router)
feature_router.include_router(health_router)
feature_router.include_router(api_v1_router)
