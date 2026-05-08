"""
arq worker registry.

Each WorkerSettings class binds one worker process group to one queue.
Concrete worker classes are added here as features are implemented.

Adding a new domain:
    1. Add a QueueName member in names.py
    2. Create the job function(s) in the owning feature or lib module
    3. Add a WorkerSettings class below bound to that queue
    4. Add an arq launch line in the startup script
"""

from typing import ClassVar
from urllib.parse import urlparse

from arq.connections import RedisSettings

from app.core.config import environment
from app.core.queue.names import QueueName
from app.features.media import prepare_media_job, warm_media_worker
from app.features.rembg import remove_background_job, warm_rembg_worker


def _redis_settings_from_url(url: str) -> RedisSettings:
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or "0"),
        password=parsed.password,
    )


_redis = _redis_settings_from_url(environment.REDIS_URL)


class MediaWorkerSettings:
    functions: ClassVar[list] = [prepare_media_job]
    redis_settings = _redis
    queue_name = QueueName.media
    on_startup = warm_media_worker
    max_jobs = 1
    job_timeout = 180
    keep_result = 0
    max_tries = 3


class BackgroundRemovalWorkerSettings:
    functions: ClassVar[list] = [remove_background_job]
    redis_settings = _redis
    queue_name = QueueName.compute
    on_startup = warm_rembg_worker
    max_jobs = 1
    job_timeout = 300
    keep_result = 0
    max_tries = 3
