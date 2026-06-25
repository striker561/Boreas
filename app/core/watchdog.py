"""
Worker process watchdog.

Monitors arq worker heartbeats in Redis and restarts workers whose heartbeat
has expired (indicating the worker process is hung or dead).  Launched from
start.sh as a background process — spawns all arq workers and keeps them alive.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from typing import TypedDict

from app.core.config import environment
from app.core.worker_heartbeats import (
    COMPUTE_HEARTBEAT_TTL,
    HEARTBEAT_SCAN_PATTERN,
    MEDIA_HEARTBEAT_TTL,
    QUEUE_COMPUTE,
    QUEUE_MEDIA,
)

CHECK_INTERVAL = 60  # seconds between heartbeat scans
SIGTERM_GRACE = 10  # seconds to wait after SIGTERM before SIGKILL
STARTUP_GRACE = 120  # seconds before requiring a heartbeat after spawn

# ── Global: track children so we can clean up on exit ──────────────────
_child_pids: list[int] = []


class WorkerConfig(TypedDict):
    settings_class: str
    heartbeat_ttl: int
    queue: str
    worker_count: int


def _worker_definitions() -> list[WorkerConfig]:
    """Build the worker list from application settings."""
    return [
        {
            "settings_class": "app.core.queue.registry.MediaWorkerSettings",
            "heartbeat_ttl": MEDIA_HEARTBEAT_TTL,
            "queue": QUEUE_MEDIA,
            "worker_count": environment.MEDIA_WORKERS,
        },
        {
            "settings_class": "app.core.queue.registry.BackgroundRemovalWorkerSettings",
            "heartbeat_ttl": COMPUTE_HEARTBEAT_TTL,
            "queue": QUEUE_COMPUTE,
            "worker_count": environment.BACKGROUND_REMOVAL_WORKERS,
        },
    ]


def _redis_client(redis_url: str):
    """Build a lightweight Redis client from the configured Redis URL."""
    import redis.asyncio as aioredis

    return aioredis.from_url(
        redis_url,
        single_connection_client=True,
    )


async def _scan_heartbeats(r):
    """Return dict mapping Redis key -> parsed JSON payload for all heartbeat keys."""
    raw: dict[str, dict] = {}
    async for key in r.scan_iter(match=HEARTBEAT_SCAN_PATTERN, count=100):
        val = await r.get(key)
        if val is None:
            continue
        if isinstance(val, bytes):
            val = val.decode()
        raw[key] = json.loads(val)
    return raw


def _spawn_worker(arq_bin: str, settings_class: str) -> int:
    """Launch an arq worker process and return its PID."""
    proc = subprocess.Popen(
        [arq_bin, settings_class],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    _child_pids.append(proc.pid)
    return proc.pid


def _kill_worker(pid: int, grace: int = SIGTERM_GRACE) -> None:
    """Send SIGTERM, wait *grace* seconds, then SIGKILL if still alive."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.2)

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _cleanup_children() -> None:
    """Kill all spawned worker processes."""
    for pid in _child_pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
    time.sleep(2)
    for pid in _child_pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
    _child_pids.clear()


def _install_signal_handlers() -> None:
    """Install signal handlers that clean up children before exit."""

    def _handler(signum: int, _frame) -> None:  # type: ignore[no-untyped-def]
        print(
            f"[watchdog] received signal {signum}, shutting down children", flush=True
        )
        _cleanup_children()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


async def watchdog_loop(arq_bin: str) -> None:
    """Main watchdog loop — runs forever until the parent process exits."""
    workers = _worker_definitions()
    spawned: dict[int, dict] = {}  # pid -> worker state

    def _spawn_configured(worker_cfg: WorkerConfig) -> None:
        for _ in range(worker_cfg["worker_count"]):
            pid = _spawn_worker(arq_bin, worker_cfg["settings_class"])
            spawned[pid] = {
                "cfg": worker_cfg,
                "spawned_at": time.monotonic(),
            }
            print(
                f"[watchdog] spawned {worker_cfg['settings_class']} pid={pid}",
                flush=True,
            )

    for cfg in workers:
        _spawn_configured(cfg)

    while True:
        try:
            r = await _redis_client(environment.REDIS_URL)
            heartbeats = await _scan_heartbeats(r)
            heartbeat_ttls: dict[int, int] = {}
            for key, data in heartbeats.items():
                pid = data.get("pid", 0)
                if not pid:
                    continue
                ttl = await r.ttl(key)
                heartbeat_ttls[pid] = ttl if ttl is not None else -1
            await r.aclose()
        except Exception as exc:
            print(f"[watchdog] Redis scan failed: {exc}", flush=True)
            await asyncio.sleep(CHECK_INTERVAL)
            continue

        now = time.monotonic()
        for pid, state in list(spawned.items()):
            cfg = state["cfg"]
            alive = True
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                alive = False
                print(
                    f"[watchdog] worker pid={pid} ({cfg['settings_class']}) "
                    f"is dead — respawning",
                    flush=True,
                )

            if alive:
                within_startup_grace = (now - state["spawned_at"]) < STARTUP_GRACE
                ttl = heartbeat_ttls.get(pid, -1)
                heartbeat_missing = pid not in heartbeat_ttls
                heartbeat_expired = ttl <= 0

                if not within_startup_grace and (
                    heartbeat_missing or heartbeat_expired
                ):
                    print(
                        f"[watchdog] worker pid={pid} ({cfg['settings_class']}) "
                        f"heartbeat stale (ttl={ttl}) — killing and respawning",
                        flush=True,
                    )
                    _kill_worker(pid)
                    alive = False

            if not alive:
                del spawned[pid]
                try:
                    _child_pids.remove(pid)
                except ValueError:
                    pass
                new_pid = _spawn_worker(arq_bin, cfg["settings_class"])
                spawned[new_pid] = {
                    "cfg": cfg,
                    "spawned_at": time.monotonic(),
                }
                print(
                    f"[watchdog] respawned {cfg['settings_class']} "
                    f"old_pid={pid} new_pid={new_pid}",
                    flush=True,
                )

        await asyncio.sleep(CHECK_INTERVAL)


def main() -> None:
    """Entry point for watchdog process."""
    if len(sys.argv) < 2:
        print("Usage: python -m app.core.watchdog <arq_bin_path>", file=sys.stderr)
        sys.exit(1)

    arq_bin = sys.argv[1]
    _install_signal_handlers()

    try:
        asyncio.run(watchdog_loop(arq_bin))
    except KeyboardInterrupt:
        _cleanup_children()


if __name__ == "__main__":
    main()
