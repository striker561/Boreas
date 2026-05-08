import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import lru_cache, partial
from typing import Any

import fcntl
from rembg import new_session, remove

from app.core.config import logger
from app.core.config.environment import get_environment

MODEL_LOCK_FILENAME = ".boreas-rembg-model.lock"


def _get_u2net_home() -> str:
    return os.environ.get("U2NET_HOME", os.path.expanduser("~/.u2net"))


@contextmanager
def _rembg_model_lock():
    os.makedirs(_get_u2net_home(), exist_ok=True)
    lock_path = os.path.join(_get_u2net_home(), MODEL_LOCK_FILENAME)
    wait_started_at = time.monotonic()

    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        wait_duration = time.monotonic() - wait_started_at
        if wait_duration >= 1.0:
            logger.info(
                "rembg model initialization lock acquired after wait",
                wait_seconds=round(wait_duration, 2),
                model=get_environment().REMBG_MODEL,
            )
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@lru_cache(maxsize=1)
def get_rembg_session() -> Any:
    with _rembg_model_lock():
        return new_session(get_environment().REMBG_MODEL)


@lru_cache(maxsize=1)
def get_rembg_remove_options() -> dict[str, Any]:
    environment = get_environment()
    return {
        "alpha_matting": environment.REMBG_ALPHA_MATTING,
        "alpha_matting_foreground_threshold": (
            environment.REMBG_ALPHA_MATTING_FOREGROUND_THRESHOLD
        ),
        "alpha_matting_background_threshold": (
            environment.REMBG_ALPHA_MATTING_BACKGROUND_THRESHOLD
        ),
        "alpha_matting_erode_size": environment.REMBG_ALPHA_MATTING_ERODE_SIZE,
        "post_process_mask": environment.REMBG_POST_PROCESS_MASK,
        "force_return_bytes": True,
    }


@lru_cache(maxsize=1)
def get_rembg_executor() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="rembg")


def warm_rembg_session() -> None:
    get_rembg_session()
    get_rembg_remove_options()
    get_rembg_executor()


def _remove_background(image_bytes: bytes) -> bytes:
    result = remove(
        image_bytes,
        session=get_rembg_session(),
        **get_rembg_remove_options(),
    )
    if not isinstance(result, bytes):
        raise TypeError("rembg did not return bytes")
    return result


async def remove_background_image(image_bytes: bytes) -> bytes:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        get_rembg_executor(),
        partial(_remove_background, image_bytes),
    )
