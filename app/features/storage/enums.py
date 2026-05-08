from enum import StrEnum


class JobStatus(StrEnum):
    queued = "queued"
    preparing = "preparing"
    processing = "processing"
    complete = "complete"
    failed = "failed"


RESULT_CONTENT_TYPE = "image/png"
TERMINAL_JOB_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.complete,
        JobStatus.failed,
    }
)
