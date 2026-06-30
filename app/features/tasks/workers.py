from typing import Any

from app.core.config import logger
from app.features.tasks.dependency import build_tasks_cleanup_service

TASKS_CLEANUP_SERVICE_CONTEXT_KEY = "tasks_cleanup_service"


async def cleanup_expired_artifacts(ctx: dict[str, Any]) -> None:
    service = ctx.get(TASKS_CLEANUP_SERVICE_CONTEXT_KEY)
    if service is None:
        service = build_tasks_cleanup_service()
        ctx[TASKS_CLEANUP_SERVICE_CONTEXT_KEY] = service
    summary = await service.run_hourly_cleanup()
    logger.info(
        "Hourly cleanup complete",
        redis_jobs_deleted=summary.redis_jobs_deleted,
        s3_objects_deleted=summary.s3_objects_deleted,
    )
