from typing import Any

from app.core.config import logger
from app.core.queue import get_arq_pool
from app.features.media.dependency import build_media_service

MEDIA_SERVICE_CONTEXT_KEY = "media_service"


async def warm_media_worker(ctx: dict[str, Any]) -> None:
    queue_pool = await get_arq_pool()
    ctx[MEDIA_SERVICE_CONTEXT_KEY] = build_media_service(queue_pool=queue_pool)
    logger.info("Media ingest worker ready")


async def ingest_media_job(ctx: dict[str, Any], job_id: str) -> None:
    media = ctx.get(MEDIA_SERVICE_CONTEXT_KEY)
    if media is None:
        queue_pool = await get_arq_pool()
        media = build_media_service(queue_pool=queue_pool)
        ctx[MEDIA_SERVICE_CONTEXT_KEY] = media
    try:
        await media.ingest_job(job_id)
    except Exception:
        logger.exception("Media ingest job failed", job_id=job_id)
        if int(ctx.get("job_try", 1)) >= 3:
            await media.fail_job(job_id, "Media ingest failed")
        raise
