from typing import Any

from app.core.config import logger
from app.core.queue import get_arq_pool
from app.features.media.dependency import build_media_service


async def warm_media_worker(ctx: dict[str, Any]) -> None:
    del ctx
    logger.info("Media worker ready")


async def prepare_media_job(ctx: dict[str, Any], job_id: str) -> None:
    queue_pool = await get_arq_pool()
    media = build_media_service(queue_pool=queue_pool)
    try:
        await media.prepare_job(job_id)
    except Exception:
        logger.exception("Media preparation job failed", job_id=job_id)
        if int(ctx.get("job_try", 1)) >= 3:
            await media.fail_job(job_id, "Media preparation failed")
        raise
