from datetime import datetime

from pydantic import BaseModel

from app.features.storage.enums import RembgJobStatus


class RembgJobQueuedResponse(BaseModel):
    job_id: str
    status: RembgJobStatus


class RembgJobResponse(BaseModel):
    job_id: str
    status: RembgJobStatus
    result_url: str | None = None
    error: str | None = None
    attempts: int
    created_at: datetime
    updated_at: datetime
