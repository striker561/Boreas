from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.rate_limit import API_RATE_LIMIT, limiter
from app.features.media.streams.dependency import get_media_job_stream_service
from app.features.media.streams.service import MediaJobStreamService
from app.schemas import APIErrorResponseSchema

router = APIRouter()


@router.get(
    "/jobs/{job_id}/stream",
    response_class=StreamingResponse,
    summary="Stream media job status",
    description=(
        "Open a Server-Sent Events stream for a job. Each event sends the serialized job "
        "snapshot in the SSE data field whenever the job status changes."
    ),
    responses={
        200: {
            "description": "SSE stream with JSON job snapshots.",
            "content": {
                "text/event-stream": {
                    "example": 'data: {"job_id":"3fa85f64-5717-4562-b3fc-2c963f66afa6","status":"queued"}\n\n'
                }
            },
        },
        404: {
            "model": APIErrorResponseSchema,
            "description": "The requested job id does not exist or has expired.",
        },
        429: {
            "model": APIErrorResponseSchema,
            "description": "The client exceeded the configured API rate limit.",
        },
    },
)
@limiter.limit(API_RATE_LIMIT)  # type: ignore[misc]
async def stream_media_job(
    request: Request,
    job_id: str,
    streams: MediaJobStreamService = Depends(get_media_job_stream_service),
):
    _ = request
    return StreamingResponse(
        streams.stream_events(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
