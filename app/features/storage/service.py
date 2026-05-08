from app.features.storage.dal import RembgStorageDAL
from app.features.storage.enums import CONTENT_TYPE_TO_EXTENSION, RembgJobStatus
from app.features.storage.schemas import RembgJob


class RembgStorageService:
    def __init__(self, dal: RembgStorageDAL) -> None:
        self.dal = dal
        self.ttl_seconds = dal.ttl_seconds

    def job_key(self, job_id: str) -> str:
        return f"jobs:rembg:{job_id}"

    def build_raw_object_key(self, job_id: str, content_type: str) -> str:
        extension = CONTENT_TYPE_TO_EXTENSION[content_type]
        return f"jobs/rembg/raw/{job_id}{extension}"

    def build_result_object_key(self, job_id: str) -> str:
        return f"jobs/rembg/result/{job_id}.png"

    def build_job(
        self,
        job_id: str,
        source_content_type: str,
        source_filename: str | None = None,
    ) -> RembgJob:
        return RembgJob(
            job_id=job_id,
            status=RembgJobStatus.queued,
            raw_key=self.build_raw_object_key(job_id, source_content_type),
            result_key=self.build_result_object_key(job_id),
            source_content_type=source_content_type,
            source_filename=source_filename,
        )

    async def save_job(self, job: RembgJob) -> None:
        await self.dal.save_job(self.job_key(job.job_id), job)

    async def get_job(self, job_id: str) -> RembgJob | None:
        return await self.dal.get_job(self.job_key(job_id))

    async def delete_job(self, job_id: str) -> None:
        await self.dal.delete_job(self.job_key(job_id))

    async def upload_source(self, job: RembgJob, image_bytes: bytes) -> None:
        await self.dal.upload_bytes(job.raw_key, image_bytes, job.source_content_type)

    async def download_source(self, job: RembgJob) -> bytes:
        return await self.dal.download_bytes(job.raw_key)

    async def upload_result(self, job: RembgJob, image_bytes: bytes) -> None:
        await self.dal.upload_bytes(
            job.result_key, image_bytes, job.result_content_type
        )

    async def delete_source(self, job: RembgJob) -> None:
        await self.dal.delete_object(job.raw_key)

    async def source_exists(self, job: RembgJob) -> bool:
        return await self.dal.object_exists(job.raw_key)

    async def result_exists(self, job: RembgJob) -> bool:
        return await self.dal.object_exists(job.result_key)

    async def get_result_url(self, job: RembgJob) -> str:
        return await self.dal.get_read_url(job.result_key)
