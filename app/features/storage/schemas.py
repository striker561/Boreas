from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.features.storage.enums import RESULT_CONTENT_TYPE, RembgJobStatus


def utcnow() -> datetime:
    return datetime.now(UTC)


class RembgJob(BaseModel):
    job_id: str
    status: RembgJobStatus
    raw_key: str
    result_key: str
    source_content_type: str
    result_content_type: str = RESULT_CONTENT_TYPE
    source_filename: str | None = None
    error: str | None = None
    attempts: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def touch(self) -> None:
        self.updated_at = utcnow()

    def mark_processing(self) -> None:
        self.status = RembgJobStatus.processing
        self.attempts += 1
        self.error = None
        self.touch()

    def mark_complete(self) -> None:
        self.status = RembgJobStatus.complete
        self.error = None
        self.touch()

    def mark_failed(self, error: str) -> None:
        self.status = RembgJobStatus.failed
        self.error = error
        self.touch()
