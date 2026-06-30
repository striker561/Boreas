from functools import lru_cache

from app.core.storage import build_media_storage_service, get_redis_cache
from app.features.tasks.service import TasksCleanupService


@lru_cache(maxsize=1)
def build_tasks_cleanup_service() -> TasksCleanupService:
    return TasksCleanupService(
        storage=build_media_storage_service(),
        redis_cache=get_redis_cache(),
    )
