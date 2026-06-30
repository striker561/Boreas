import json
from collections.abc import AsyncGenerator

from app.core.storage import TERMINAL_JOB_STATUSES
from app.features.media.schemas import MediaJobResponse
from app.features.media.service import MediaService
from app.features.media.streams.hub import JobNotifyHub


class MediaJobStreamService:
    def __init__(self, media: MediaService, hub: JobNotifyHub) -> None:
        self._media = media
        self._hub = hub

    async def stream_events(self, job_id: str) -> AsyncGenerator[str, None]:
        previous_payload: str | None = None
        notify = self._hub.subscribe(job_id)

        async def maybe_emit() -> tuple[str | None, MediaJobResponse]:
            nonlocal previous_payload
            payload = await self._media.require_job_response(job_id)
            serialized_payload = json.dumps(payload.model_dump(mode="json"))
            if serialized_payload == previous_payload:
                return None, payload

            previous_payload = serialized_payload
            return f"data: {serialized_payload}\n\n", payload

        try:
            event, payload = await maybe_emit()
            if event:
                yield event
            if payload.status in TERMINAL_JOB_STATUSES:
                return

            # ponytail: no poll fallback; hub wakes streams when save_job publishes
            while True:
                await notify.wait()
                notify.clear()

                event, payload = await maybe_emit()
                if event:
                    yield event
                if payload.status in TERMINAL_JOB_STATUSES:
                    return
        finally:
            self._hub.unsubscribe(job_id, notify)
