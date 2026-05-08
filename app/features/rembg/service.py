from app.core.config import logger
from app.core.storage import MediaStorageService
from app.lib.rembg import remove_background_image, warm_rembg_session


class BackgroundRemovalProcessor:
    def __init__(self, storage: MediaStorageService) -> None:
        self.storage = storage

    def warm_worker_dependencies(self) -> None:
        warm_rembg_session()

    async def process_job(self, job_id: str) -> None:
        job = await self.storage.get_job(job_id)
        if job is None:
            logger.warning("Background removal job missing in Redis", job_id=job_id)
            return

        if await self.storage.result_exists(job):
            job.mark_complete()
            await self.storage.save_job(job)
            if await self.storage.source_exists(job):
                await self._delete_source_safely(job)
            return

        if not await self.storage.source_exists(job):
            await self.fail_job(job_id, "Source upload is missing")
            return

        job.mark_processing()
        await self.storage.save_job(job)

        raw_image = await self.storage.download_source(job)
        output_image = await remove_background_image(raw_image)
        await self.storage.upload_result(job, output_image)
        await self._delete_source_safely(job)

        job.mark_complete()
        await self.storage.save_job(job)

    async def fail_job(self, job_id: str, error: str) -> None:
        job = await self.storage.get_job(job_id)
        if job is None:
            return

        job.mark_failed(error)
        await self.storage.save_job(job)

    async def _delete_source_safely(self, job) -> None:
        try:
            await self.storage.delete_source(job)
        except Exception as exc:
            logger.warning(
                "Failed to delete prepared source object",
                job_id=job.job_id,
                error=type(exc).__name__,
            )
