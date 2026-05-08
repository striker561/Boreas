import asyncio
from functools import lru_cache, partial
from typing import Any

from rembg import new_session, remove

from app.core.config.environment import get_environment


@lru_cache(maxsize=1)
def get_rembg_session() -> Any:
    return new_session(get_environment().REMBG_MODEL)


def warm_rembg_session() -> None:
    get_rembg_session()


def _remove_background(image_bytes: bytes) -> bytes:
    result = remove(image_bytes, session=get_rembg_session())
    if not isinstance(result, bytes):
        raise TypeError("rembg did not return bytes")
    return result


async def remove_background_image(image_bytes: bytes) -> bytes:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_remove_background, image_bytes))
