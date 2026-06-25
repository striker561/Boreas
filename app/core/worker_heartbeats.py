"""Shared worker heartbeat keys and TTLs for ARQ workers, watchdog, and health."""

from __future__ import annotations

import json
import os
from typing import Any

from app.core.config import logger

MEDIA_HEARTBEAT_KEY_TPL = "heartbeat:worker:media:{pid}"
COMPUTE_HEARTBEAT_KEY_TPL = "heartbeat:worker:compute:{pid}"
MEDIA_HEARTBEAT_TTL = 360
COMPUTE_HEARTBEAT_TTL = 600
HEARTBEAT_SCAN_PATTERN = "heartbeat:worker:*"

QUEUE_MEDIA = "media"
QUEUE_COMPUTE = "compute"

HEARTBEAT_TTL_BY_QUEUE: dict[str, int] = {
    QUEUE_MEDIA: MEDIA_HEARTBEAT_TTL,
    QUEUE_COMPUTE: COMPUTE_HEARTBEAT_TTL,
}

HEARTBEAT_KEY_TPL_BY_QUEUE: dict[str, str] = {
    QUEUE_MEDIA: MEDIA_HEARTBEAT_KEY_TPL,
    QUEUE_COMPUTE: COMPUTE_HEARTBEAT_KEY_TPL,
}


async def write_worker_heartbeat(
    ctx: dict[str, Any],
    *,
    queue: str,
    job_id: str | None = None,
) -> None:
    """Write or refresh a worker heartbeat in Redis."""
    try:
        pid = os.getpid()
        key = HEARTBEAT_KEY_TPL_BY_QUEUE[queue].format(pid=pid)
        ttl = HEARTBEAT_TTL_BY_QUEUE[queue]
        payload = json.dumps(
            {
                "pid": pid,
                "queue": queue,
                "last_job_id": job_id or "",
            },
            separators=(",", ":"),
        )
        await ctx["redis"].set(key, payload, ex=ttl)
    except Exception:
        logger.debug("Failed to write worker heartbeat", exc_info=True)
