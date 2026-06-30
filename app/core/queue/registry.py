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

from arq.cron import cron

from app.core.config import environment
from app.core.queue.names import QueueName
from app.core.queue.pool import build_arq_redis_settings
from app.features.media import ingest_media_job, warm_media_worker
from app.features.rembg import (
    remove_background_job,
    warm_background_removal_worker,
)
from app.features.tasks import cleanup_expired_artifacts

_redis = build_arq_redis_settings(environment.REDIS_URL)


class MediaWorkerSettings:
    functions: ClassVar[list] = [ingest_media_job]
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
    on_startup = warm_background_removal_worker
    max_jobs = 1
    job_timeout = 300
    keep_result = 0
    max_tries = 3


class TasksWorkerSettings:
    functions: ClassVar[list] = [cleanup_expired_artifacts]
    cron_jobs = [
        cron(
            cleanup_expired_artifacts,
            minute=0,
            unique=True,
            timeout=600,
        ),
    ]
    redis_settings = _redis
    queue_name = QueueName.tasks
    max_jobs = 1
    job_timeout = 600
    keep_result = 0
    max_tries = 1
