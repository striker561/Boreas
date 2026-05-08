import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse

from app.core.rate_limit import rate_limit_default, rate_limit_upload
from app.features.media.dependency import get_media_service
from app.features.media.service import MediaService
from app.features.storage import TERMINAL_JOB_STATUSES
from app.helpers import APIResponse

router = APIRouter(prefix="/media", tags=["Media"])


@router.post("/jobs/bg", dependencies=[Depends(rate_limit_upload)])
async def create_media_bg_job(
    file: UploadFile = File(...),
    media: MediaService = Depends(get_media_service),
):
    payload = await media.create_job(file)
    return APIResponse.created(
        msg="Media job queued",
        data=payload,
    )


@router.get("/jobs/{job_id}", dependencies=[Depends(rate_limit_default)])
async def get_media_job(
    job_id: str,
    media: MediaService = Depends(get_media_service),
):
    payload = await media.require_job_response(job_id)
    return APIResponse.success(data=payload)


@router.get("/jobs/{job_id}/stream", dependencies=[Depends(rate_limit_default)])
async def stream_media_job(
    job_id: str,
    media: MediaService = Depends(get_media_service),
):
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

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
