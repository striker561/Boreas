from enum import StrEnum


class JobStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    complete = "complete"
    failed = "failed"


CONTENT_TYPE_TO_EXTENSION: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
RESULT_CONTENT_TYPE = "image/png"
TERMINAL_JOB_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.complete,
        JobStatus.failed,
    }
)
