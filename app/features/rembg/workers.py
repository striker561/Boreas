from typing import Any

from app.core.config import logger
from app.features.rembg.dependency import build_background_removal_processor

BACKGROUND_REMOVAL_PROCESSOR_CONTEXT_KEY = "background_removal_processor"


async def warm_background_removal_worker(ctx: dict[str, Any]) -> None:
    processor = build_background_removal_processor()
    prewarmed = True
    try:
        processor.warm_worker_dependencies()
    except Exception as exc:
        prewarmed = False
        logger.warning(
            "Background removal worker warmup failed; model will load on first job",
            error=type(exc).__name__,
        )
    ctx[BACKGROUND_REMOVAL_PROCESSOR_CONTEXT_KEY] = processor
    logger.info("Background removal worker ready", prewarmed=prewarmed)


async def remove_background_job(ctx: dict[str, Any], job_id: str) -> None:
    processor = ctx.get(BACKGROUND_REMOVAL_PROCESSOR_CONTEXT_KEY)
    if processor is None:
        processor = build_background_removal_processor()
        ctx[BACKGROUND_REMOVAL_PROCESSOR_CONTEXT_KEY] = processor
    try:
        await processor.process_job(job_id)
    except Exception:
        logger.exception("Background removal job failed", job_id=job_id)
        if int(ctx.get("job_try", 1)) >= 3:
            await processor.fail_job(job_id, "Background removal failed")
        raise
