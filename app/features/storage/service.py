from app.features.storage.dal import StorageDAL
from app.features.storage.enums import JobStatus
from app.features.storage.schemas import MediaJob


class MediaStorageService:
    def __init__(
        self,
        dal: StorageDAL,
        *,
        staged_upload_ttl_seconds: int,
    ) -> None:
        self.dal = dal
        self.ttl_seconds = dal.ttl_seconds
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
        await self.dal.save_job(self.job_key(job.job_id), job)

    async def get_job(self, job_id: str) -> MediaJob | None:
        return await self.dal.get_job(self.job_key(job_id))

    async def delete_job(self, job_id: str) -> None:
        await self.dal.delete_job(self.job_key(job_id))

    async def save_staged_upload(
        self,
        job_id: str,
        payload: dict[str, object],
    ) -> None:
        await self.dal.save_staged_upload(
            self.staged_upload_key(job_id),
            payload,
            ttl_seconds=self.staged_upload_ttl_seconds,
        )

    async def get_staged_upload(self, job_id: str) -> dict[str, object] | None:
        return await self.dal.get_staged_upload(self.staged_upload_key(job_id))

    async def delete_staged_upload(self, job_id: str) -> None:
        await self.dal.delete_staged_upload(self.staged_upload_key(job_id))

    async def upload_source(
        self,
        job: MediaJob,
        image_bytes: bytes,
        content_type: str | None = None,
    ) -> None:
        await self.dal.upload_bytes(
            job.source_key,
            image_bytes,
            content_type or job.source_content_type,
        )

    async def download_source(self, job: MediaJob) -> bytes:
        return await self.dal.download_bytes(job.source_key)

    async def upload_result(self, job: MediaJob, image_bytes: bytes) -> None:
        await self.dal.upload_bytes(
            job.result_key, image_bytes, job.result_content_type
        )

    async def delete_source(self, job: MediaJob) -> None:
        await self.dal.delete_object(job.source_key)

    async def source_exists(self, job: MediaJob) -> bool:
        return await self.dal.object_exists(job.source_key)

    async def result_exists(self, job: MediaJob) -> bool:
        return await self.dal.object_exists(job.result_key)

    async def get_result_url(self, job: MediaJob) -> str:
        return await self.dal.get_read_url(job.result_key)
