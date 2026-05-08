import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.core.storage import TERMINAL_JOB_STATUSES
from app.core.rate_limit import API_RATE_LIMIT, UPLOAD_RATE_LIMIT, limiter
from app.features.media.dependency import get_media_service
from app.features.media.service import MediaService
from app.helpers import APIResponse

router = APIRouter(prefix="/media", tags=["Media"])
STREAM_POLL_INTERVAL_SECONDS = 2.0


@router.post("/jobs")
@limiter.limit(UPLOAD_RATE_LIMIT)  # type: ignore[misc]
async def create_media_job(
    request: Request,
    file: UploadFile = File(...),
    media: MediaService = Depends(get_media_service),
):
    _ = request
    payload = await media.create_job(file)
    return APIResponse.created(
        msg="Media job queued",
        data=payload,
    )


@router.get("/jobs/{job_id}")
@limiter.limit(API_RATE_LIMIT)  # type: ignore[misc]
async def get_media_job(
    request: Request,
    job_id: str,
    media: MediaService = Depends(get_media_service),
):
    _ = request
    payload = await media.require_job_response(job_id)
    return APIResponse.success(data=payload)


@router.get("/jobs/{job_id}/stream")
@limiter.limit(API_RATE_LIMIT)  # type: ignore[misc]
async def stream_media_job(
    request: Request,
    job_id: str,
    media: MediaService = Depends(get_media_service),
):
    _ = request
    await media.require_job_response(job_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        previous_payload: str | None = None

        while True:
            payload = await media.require_job_response(job_id)
            serialized_payload = json.dumps(payload.model_dump(mode="json"))

            if serialized_payload != previous_payload:
                yield f"data: {serialized_payload}\n\n"
                previous_payload = serialized_payload

            if payload.status in TERMINAL_JOB_STATUSES:
                break

            await asyncio.sleep(STREAM_POLL_INTERVAL_SECONDS)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
