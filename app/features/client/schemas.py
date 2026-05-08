from datetime import datetime

from pydantic import BaseModel

from app.features.storage.enums import JobStatus


class JobQueuedResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    result_url: str | None = None
    error: str | None = None
    attempts: int
    created_at: datetime
    updated_at: datetime
