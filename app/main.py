from typing import Any

from fastapi.responses import JSONResponse

from app.core import app
from app.core import environment, get_arq_pool, get_redis_cache
from app.core.queue import QueueName
from app.core.storage import build_media_storage_service
from app.features.routes import feature_router
from app.helpers.responses import APIResponse
from app.schemas import APIResponseSchema


@app.get(
    "/",
    tags=["Status"],
    response_model=APIResponseSchema,
)
def status_check() -> JSONResponse:
    """Application status"""
    return APIResponse.success(
        msg="Application healthy",
        data={"status": "ok"},
    )


@app.get(
    "/health",
    tags=["Status"],
    response_model=APIResponseSchema,
)
async def public_health() -> JSONResponse:
    """Public health endpoint with queue and staging metrics."""
    redis_cache = get_redis_cache()
    redis_ok = await redis_cache.ping()

    try:
        arq_pool = await get_arq_pool()
        arq_ok = arq_pool is not None
    except Exception:
        arq_ok = False

    storage = build_media_storage_service()
    queue_depths: dict[str, int] = {
        QueueName.media.value: await storage.queue_depth(QueueName.media.value),
        QueueName.compute.value: await storage.queue_depth(QueueName.compute.value),
    }
    staged_uploads = await storage.staged_upload_count()

    data: dict[str, Any] = {
        "status": "ok" if redis_ok and arq_ok else "degraded",
        "redis": {"reachable": redis_ok},
        "arq": {"reachable": arq_ok},
        "queue_depths": queue_depths,
        "staged_uploads": staged_uploads,
        "workers": {
            "media": environment.MEDIA_WORKERS,
            "background_removal": environment.BACKGROUND_REMOVAL_WORKERS,
        },
        "limits": {
            "job_ttl_seconds": environment.JOB_TTL_SECONDS,
            "result_url_ttl_seconds": environment.RESULT_URL_TTL_SECONDS,
            "media_source_max_bytes": environment.MEDIA_SOURCE_MAX_BYTES,
        },
    }
    status_code = 200 if redis_ok and arq_ok else 503
    return APIResponse.success(
        msg="Application health",
        data=data,
        status=status_code,
    )


# Register all feature routers
app.include_router(feature_router)
