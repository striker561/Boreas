import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse

from app.core.rate_limit import rate_limit_default, rate_limit_upload
from app.features.client.dependency import get_client_service
from app.features.client.service import ClientService
from app.features.storage import TERMINAL_JOB_STATUSES
from app.helpers import APIResponse

router = APIRouter()


@router.post("/remove-bg", dependencies=[Depends(rate_limit_upload)])
async def submit_rembg_job(
    file: UploadFile = File(...),
    client: ClientService = Depends(get_client_service),
):
    payload = await client.create_job(file)
    return APIResponse.created(
        msg="Background removal job queued",
        data=payload,
    )


@router.get("/jobs/{job_id}", dependencies=[Depends(rate_limit_default)])
async def get_rembg_job(
    job_id: str,
    client: ClientService = Depends(get_client_service),
):
    payload = await client.require_job_response(job_id)
    return APIResponse.success(data=payload)


@router.get("/jobs/{job_id}/stream", dependencies=[Depends(rate_limit_default)])
async def stream_rembg_job(
    job_id: str,
    client: ClientService = Depends(get_client_service),
):
    await client.require_job_response(job_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        previous_payload: str | None = None

        while True:
            payload = await client.require_job_response(job_id)
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
