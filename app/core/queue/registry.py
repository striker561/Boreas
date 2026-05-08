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

from urllib.parse import urlparse

from arq.connections import RedisSettings

from app.core.config import environment
from app.core.queue.names import QueueName


def _redis_settings_from_url(url: str) -> RedisSettings:
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or "0"),
        password=parsed.password,
    )


_redis = _redis_settings_from_url(environment.REDIS_URL)


