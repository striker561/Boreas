from fastapi import Depends

from app.features.media.dependency import get_media_service
from app.features.media.service import MediaService
from app.features.media.streams.hub import get_job_notify_hub
from app.features.media.streams.service import MediaJobStreamService


def build_media_job_stream_service(
    media: MediaService,
) -> MediaJobStreamService:
    return MediaJobStreamService(media=media, hub=get_job_notify_hub())


async def get_media_job_stream_service(
    media: MediaService = Depends(get_media_service),
) -> MediaJobStreamService:
    return build_media_job_stream_service(media=media)
