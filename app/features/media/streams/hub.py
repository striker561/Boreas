import asyncio
from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import environment, logger

MEDIA_JOB_NOTIFY_PATTERN = "jobs:media:*:notify"
_JOB_NOTIFY_PREFIX = "jobs:media:"
_JOB_NOTIFY_SUFFIX = ":notify"


def job_id_from_notify_channel(channel: str) -> str | None:
    if not channel.startswith(_JOB_NOTIFY_PREFIX) or not channel.endswith(
        _JOB_NOTIFY_SUFFIX
    ):
        return None
    job_id = channel[len(_JOB_NOTIFY_PREFIX) : -len(_JOB_NOTIFY_SUFFIX)]
    return job_id or None


class JobNotifyHub:
    """One Redis PSUBSCRIBE per process; SSE streams wait in memory by job_id."""

    def __init__(self) -> None:
        self._waiters: dict[str, set[asyncio.Event]] = {}
        self._task: asyncio.Task[None] | None = None

    def subscribe(self, job_id: str) -> asyncio.Event:
        event = asyncio.Event()
        self._waiters.setdefault(job_id, set()).add(event)
        return event

    def unsubscribe(self, job_id: str, event: asyncio.Event) -> None:
        waiters = self._waiters.get(job_id)
        if not waiters:
            return
        waiters.discard(event)
        if not waiters:
            del self._waiters[job_id]

    def wake(self, job_id: str) -> None:
        for event in self._waiters.get(job_id, ()):
            event.set()

    def stats(self) -> dict[str, int | bool]:
        task = self._task
        return {
            "active_streams": sum(len(waiters) for waiters in self._waiters.values()),
            "tracked_jobs": len(self._waiters),
            "listener_running": task is not None and not task.done(),
        }

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _listen(self) -> None:
        client = Redis.from_url(environment.REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.psubscribe(MEDIA_JOB_NOTIFY_PATTERN)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "pmessage":
                    continue
                channel = message.get("channel")
                if not isinstance(channel, str):
                    continue
                job_id = job_id_from_notify_channel(channel)
                if job_id:
                    self.wake(job_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "Job notify hub listener failed",
                error=type(exc).__name__,
                exc_info=True,
            )
        finally:
            await pubsub.punsubscribe(MEDIA_JOB_NOTIFY_PATTERN)
            await pubsub.aclose()
            await client.aclose()


@lru_cache(maxsize=1)
def get_job_notify_hub() -> JobNotifyHub:
    return JobNotifyHub()
