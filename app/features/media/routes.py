from typing import Annotated

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.rate_limit import API_RATE_LIMIT, UPLOAD_RATE_LIMIT, limiter
from app.core.storage import TERMINAL_JOB_STATUSES
from app.features.media.dependency import get_media_service
from app.features.media.schemas import MediaJobQueuedResponse, MediaJobResponse
from app.features.media.service import MediaService
from app.helpers import APIResponse
from app.schemas import APIErrorResponseSchema, APIResponseSchema

router = APIRouter(prefix="/media", tags=["Media"])
STREAM_POLL_INTERVAL_SECONDS = 2.0
UploadFileInput = Annotated[
    UploadFile,
    File(
        description=(
            "PNG, JPEG, or WEBP image uploaded as multipart/form-data. "
            "The request body may be up to 10 MB, image dimensions may be up to 4000x4000px, "
            "and Boreas will normalize the prepared worker input down to the configured source "
            "cap before compute begins."
        )
    ),
]


@router.post(
    "/jobs",
    response_model=APIResponseSchema[MediaJobQueuedResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a background removal job",
    description=(
        "Accept an uploaded image, validate its media constraints, stage it briefly in Redis, "
        "and enqueue the ingest worker. The API returns immediately with a job id."
    ),
    responses={
        400: {
            "model": APIErrorResponseSchema,
            "description": (
                "The uploaded file is invalid, uses an unsupported image type, or exceeds the "
                "maximum supported image dimensions."
            ),
        },
        413: {
            "model": APIErrorResponseSchema,
            "description": "The uploaded file exceeds the configured maximum request size.",
        },
        429: {
            "model": APIErrorResponseSchema,
            "description": "The client exceeded the configured upload rate limit.",
        },
        503: {
            "model": APIErrorResponseSchema,
            "description": "The job could not be staged or queued.",
        },
    },
)
@limiter.limit(UPLOAD_RATE_LIMIT)  # type: ignore[misc]
async def create_media_job(
    request: Request,
    file: UploadFileInput,
    media: MediaService = Depends(get_media_service),
):
    _ = request
    payload = await media.create_job(file)
    return APIResponse.created(
        msg="Media job queued",
        data=payload,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=APIResponseSchema[MediaJobResponse],
    summary="Get media job status",
    description=(
        "Fetch the current job lifecycle state. When the job is complete, the response "
        "includes a short-lived result URL for the final PNG."
    ),
    responses={
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
async def get_media_job(
    request: Request,
    job_id: str,
    media: MediaService = Depends(get_media_service),
):
    _ = request
    payload = await media.require_job_response(job_id)
    return APIResponse.success(data=payload)


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
