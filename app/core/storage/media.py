from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache

from fastapi import Depends
from pydantic import BaseModel, Field

from app.core.config import environment
from app.core.storage.dependency import get_redis_cache
from app.core.storage.redis import RedisCache
from app.lib.storage import StorageBackend, get_storage

RESULT_CONTENT_TYPE = "image/png"


class JobStatus(StrEnum):
    queued = "queued"
    preparing = "preparing"
    processing = "processing"
    complete = "complete"
    failed = "failed"


TERMINAL_JOB_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.complete,
        JobStatus.failed,
    }
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class MediaJob(BaseModel):
    job_id: str
    status: JobStatus
    source_key: str
    result_key: str
    source_content_type: str
    source_size_bytes: int | None = None
    result_content_type: str = RESULT_CONTENT_TYPE
    source_filename: str | None = None
    error: str | None = None
    attempts: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def touch(self) -> None:
        self.updated_at = utcnow()

    def mark_preparing(self) -> None:
        self.status = JobStatus.preparing
        self.error = None
        self.touch()

    def mark_processing(self) -> None:
        self.status = JobStatus.processing
        self.attempts += 1
        self.error = None
        self.touch()

    def mark_complete(self) -> None:
        self.status = JobStatus.complete
        self.error = None
        self.touch()

    def mark_failed(self, error: str) -> None:
        self.status = JobStatus.failed
        self.error = error
        self.touch()


class MediaStorageService:
    def __init__(
        self,
        redis_cache: RedisCache,
        object_storage: StorageBackend,
        *,
        job_ttl_seconds: int,
        result_url_ttl_seconds: int,
        staged_upload_ttl_seconds: int,
    ) -> None:
        self.redis_cache = redis_cache
        self.object_storage = object_storage
        self.job_ttl_seconds = job_ttl_seconds
        self.result_url_ttl_seconds = result_url_ttl_seconds
        self.staged_upload_ttl_seconds = staged_upload_ttl_seconds

    def job_key(self, job_id: str) -> str:
        return f"jobs:media:{job_id}"

    def build_source_object_key(self, job_id: str) -> str:
        return f"jobs/media/source/{job_id}"

    def build_result_object_key(self, job_id: str) -> str:
        return f"jobs/media/result/{job_id}.png"

    def staged_upload_key(self, job_id: str) -> str:
        return f"jobs:media:staged-upload:{job_id}"

    def build_job(
        self,
        job_id: str,
        source_content_type: str,
        source_filename: str | None = None,
        source_size_bytes: int | None = None,
    ) -> MediaJob:
        return MediaJob(
            job_id=job_id,
            status=JobStatus.queued,
            source_key=self.build_source_object_key(job_id),
            result_key=self.build_result_object_key(job_id),
            source_content_type=source_content_type,
            source_size_bytes=source_size_bytes,
            source_filename=source_filename,
        )

    async def save_job(self, job: MediaJob) -> None:
        saved = await self.redis_cache.set(
            self.job_key(job.job_id),
            job.model_dump(mode="json"),
            ttl=self.job_ttl_seconds,
        )
        if not saved:
            raise RuntimeError("Failed to persist media job in Redis")

    async def get_job(self, job_id: str) -> MediaJob | None:
        payload = await self.redis_cache.get(self.job_key(job_id))
        if payload is None:
            return None
        return MediaJob.model_validate(payload)

    async def delete_job(self, job_id: str) -> None:
        await self.redis_cache.delete(self.job_key(job_id))

    async def save_staged_upload(
        self,
        job_id: str,
        payload: dict[str, object],
    ) -> None:
        saved = await self.redis_cache.set(
            self.staged_upload_key(job_id),
            payload,
            ttl=self.staged_upload_ttl_seconds,
        )
        if not saved:
            raise RuntimeError("Failed to persist staged upload in Redis")

    async def get_staged_upload(self, job_id: str) -> dict[str, object] | None:
        payload = await self.redis_cache.get(self.staged_upload_key(job_id))
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise TypeError("Staged upload payload must be a dictionary")
        return payload

    async def delete_staged_upload(self, job_id: str) -> None:
        await self.redis_cache.delete(self.staged_upload_key(job_id))

    async def upload_source(
        self,
        job: MediaJob,
        image_bytes: bytes,
        content_type: str | None = None,
    ) -> None:
        await self.object_storage.upload_bytes(
            job.source_key,
            image_bytes,
            content_type=content_type or job.source_content_type,
        )

    async def download_source(self, job: MediaJob) -> bytes:
        return await self.object_storage.download_bytes(job.source_key)

    async def upload_result(self, job: MediaJob, image_bytes: bytes) -> None:
        await self.object_storage.upload_bytes(
            job.result_key,
            image_bytes,
            content_type=job.result_content_type,
        )

    async def delete_source(self, job: MediaJob) -> None:
        await self.object_storage.delete(job.source_key)

    async def source_exists(self, job: MediaJob) -> bool:
        return await self.object_storage.exists(job.source_key)

    async def result_exists(self, job: MediaJob) -> bool:
        return await self.object_storage.exists(job.result_key)

    async def get_result_url(self, job: MediaJob) -> str:
        return await self.object_storage.presign_read(
            job.result_key,
            expires_in=self.result_url_ttl_seconds,
        )


@lru_cache(maxsize=1)
def build_media_storage_service() -> MediaStorageService:
    return MediaStorageService(
        redis_cache=get_redis_cache(),
        object_storage=get_storage(),
        job_ttl_seconds=environment.JOB_TTL_SECONDS,
        result_url_ttl_seconds=environment.RESULT_URL_TTL_SECONDS,
        staged_upload_ttl_seconds=environment.MEDIA_STAGING_TTL_SECONDS,
    )


async def get_media_storage_service(
    storage: MediaStorageService = Depends(build_media_storage_service),
) -> MediaStorageService:
    return storage