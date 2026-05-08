import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache, partial
from typing import Any

from rembg import new_session, remove

from app.core.config.environment import get_environment


@lru_cache(maxsize=1)
def get_rembg_session() -> Any:
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
