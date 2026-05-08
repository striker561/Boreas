import unittest
from io import BytesIO
from unittest.mock import AsyncMock, patch

import os

from fastapi import HTTPException
from PIL import Image

os.environ.setdefault("APP_NAME", "Boreas")
os.environ.setdefault("APP_VERSION", "1.0.0")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("TRUSTED_HOSTS", "localhost")
os.environ.setdefault("STORAGE_ACCESS_KEY_ID", "key")
os.environ.setdefault("STORAGE_SECRET_ACCESS_KEY", "secret")
os.environ.setdefault("STORAGE_BUCKET_NAME", "bucket")

from app.core.storage import JobStatus, MediaJob, MediaStorageService
from app.features.media import service as media_service_module
from app.features.media.schemas import StagedMediaUpload
from app.features.media.service import MediaService
from app.features.rembg.service import BackgroundRemovalProcessor


class FakeQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, str, str]] = []

    async def enqueue_job(self, name: str, job_id: str, _queue_name: str) -> None:
        self.jobs.append((name, job_id, _queue_name))


class FakeStorage:
    def __init__(self, job: MediaJob | None = None) -> None:
        self.job = job
        self.saved_jobs: list[MediaJob] = []
        self.staged_payload: bytes | None = None
        self.staged_metadata: dict[str, object] | None = None
        self.uploaded_sources: list[tuple[str, bytes, str]] = []
        self.uploaded_results: list[tuple[str, bytes]] = []
        self.deleted_sources: list[str] = []
        self.deleted_staged: list[str] = []
        self.result_url_expiry: int | None = None
        self.result_exists_value = False
        self.source_exists_value = False

    def build_job(
        self,
        job_id: str,
        source_content_type: str,
        source_filename: str | None = None,
        source_size_bytes: int | None = None,
    ) -> MediaJob:
        self.job = MediaJob(
            job_id=job_id,
            status=JobStatus.queued,
            source_key=f"jobs/media/source/{job_id}",
            result_key=f"jobs/media/result/{job_id}.png",
            source_content_type=source_content_type,
            source_size_bytes=source_size_bytes,
            source_filename=source_filename,
        )
        return self.job

    async def save_job(self, job: MediaJob) -> None:
        self.job = job
        self.saved_jobs.append(job.model_copy(deep=True))

    async def get_job(self, job_id: str) -> MediaJob | None:
        if self.job and self.job.job_id == job_id:
            return self.job
        return None

    async def delete_job(self, job_id: str) -> None:
        if self.job and self.job.job_id == job_id:
            self.job = None

    async def save_staged_upload(
        self,
        job_id: str,
        *,
        payload: bytes,
        metadata: dict[str, object],
    ) -> None:
        self.staged_payload = payload
        self.staged_metadata = metadata

    async def get_staged_upload_metadata(self, job_id: str) -> dict[str, object] | None:
        return self.staged_metadata

    async def get_staged_upload_payload(self, job_id: str) -> bytes | None:
        return self.staged_payload

    async def delete_staged_upload(self, job_id: str) -> None:
        self.deleted_staged.append(job_id)
        self.staged_payload = None
        self.staged_metadata = None

    async def upload_source(
        self,
        job: MediaJob,
        image_bytes: bytes,
        content_type: str | None = None,
    ) -> None:
        self.source_exists_value = True
        self.uploaded_sources.append(
            (job.source_key, image_bytes, content_type or job.source_content_type)
        )

    async def download_source(self, job: MediaJob) -> bytes:
        if self.uploaded_sources:
            return self.uploaded_sources[-1][1]
        return b"source"

    async def upload_result(self, job: MediaJob, image_bytes: bytes) -> None:
        self.result_exists_value = True
        self.uploaded_results.append((job.result_key, image_bytes))

    async def delete_source(self, job: MediaJob) -> None:
        self.source_exists_value = False
        self.deleted_sources.append(job.source_key)

    async def source_exists(self, job: MediaJob) -> bool:
        return self.source_exists_value

    async def result_exists(self, job: MediaJob) -> bool:
        return self.result_exists_value

    async def get_result_url(self, job: MediaJob) -> str:
        self.result_url_expiry = 3600
        return "https://example.com/result.png"


class ChunkedUpload:
    def __init__(
        self,
        chunks: list[bytes],
        *,
        filename: str = "image.png",
        content_type: str = "image/png",
    ) -> None:
        self._chunks = list(chunks)
        self.filename = filename
        self.content_type = content_type
        self.closed = False

    async def read(self, size: int = -1) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    async def close(self) -> None:
        self.closed = True


class MediaFlowTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _build_png_bytes() -> bytes:
        output = BytesIO()
        Image.new("RGB", (16, 16), (255, 0, 0)).save(output, format="PNG")
        return output.getvalue()

    async def test_create_job_reads_upload_in_chunks_and_stages_payload(self) -> None:
        image_bytes = self._build_png_bytes()
        upload = ChunkedUpload([image_bytes[:10], image_bytes[10:]])
        storage = FakeStorage()
        queue = FakeQueue()
        service = MediaService(storage=storage, queue_pool=queue)  # type: ignore[arg-type]

        payload = await service.create_job(upload)  # type: ignore[arg-type]

        self.assertEqual(payload.status, JobStatus.queued)
        self.assertIsNotNone(storage.job)
        self.assertEqual(storage.staged_payload, image_bytes)
        self.assertIsNotNone(storage.staged_metadata)
        self.assertEqual(storage.staged_metadata["content_type"], "image/png")
        self.assertEqual(queue.jobs[0][2], "boreas:media")
        self.assertTrue(upload.closed)

    async def test_create_job_rejects_oversized_upload_before_processing(self) -> None:
        upload = ChunkedUpload([b"aa", b"bb", b"c"])
        storage = FakeStorage()
        queue = FakeQueue()
        service = MediaService(storage=storage, queue_pool=queue)  # type: ignore[arg-type]

        with patch.object(media_service_module.environment, "MAX_BODY_SIZE", 4):
            with self.assertRaises(HTTPException) as ctx:
                await service.create_job(upload)  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.status_code, 413)
        self.assertEqual(queue.jobs, [])
        self.assertIsNone(storage.staged_payload)
        self.assertTrue(upload.closed)

    async def test_ingest_job_uploads_source_and_clears_staging(self) -> None:
        job = MediaJob(
            job_id="job-1",
            status=JobStatus.queued,
            source_key="jobs/media/source/job-1",
            result_key="jobs/media/result/job-1.png",
            source_content_type="image/png",
        )
        storage = FakeStorage(job=job)
        staged = StagedMediaUpload(
            filename="image.png",
            payload=b"payload",
            content_type="image/png",
            size_bytes=7,
            width=32,
            height=32,
        )
        storage.staged_payload = staged.payload
        storage.staged_metadata = {
            "filename": staged.filename,
            "content_type": staged.content_type,
            "size_bytes": staged.size_bytes,
            "width": staged.width,
            "height": staged.height,
        }
        queue = FakeQueue()
        service = MediaService(storage=storage, queue_pool=queue)  # type: ignore[arg-type]

        await service.ingest_job("job-1")

        self.assertEqual(job.status, JobStatus.preparing)
        self.assertEqual(len(storage.uploaded_sources), 1)
        self.assertEqual(storage.deleted_staged, ["job-1"])
        self.assertEqual(queue.jobs[0][2], "boreas:compute")

    async def test_background_removal_uploads_result_and_deletes_source(self) -> None:
        job = MediaJob(
            job_id="job-2",
            status=JobStatus.preparing,
            source_key="jobs/media/source/job-2",
            result_key="jobs/media/result/job-2.png",
            source_content_type="image/png",
        )
        storage = FakeStorage(job=job)
        storage.source_exists_value = True
        processor = BackgroundRemovalProcessor(storage=storage)  # type: ignore[arg-type]

        with patch(
            "app.features.rembg.service.remove_background_image",
            new=AsyncMock(return_value=b"result-bytes"),
        ):
            await processor.process_job("job-2")

        self.assertEqual(job.status, JobStatus.complete)
        self.assertEqual(len(storage.uploaded_results), 1)
        self.assertEqual(storage.deleted_sources, ["jobs/media/source/job-2"])

    async def test_result_url_assumption_is_one_hour(self) -> None:
        storage_backend = AsyncMock()
        storage_backend.presign_read.return_value = "https://example.com/result.png"
        redis_cache = AsyncMock()
        service = MediaStorageService(
            redis_cache=redis_cache,
            object_storage=storage_backend,
            job_ttl_seconds=3600,
            result_url_ttl_seconds=3600,
            staged_upload_ttl_seconds=900,
        )
        job = MediaJob(
            job_id="job-3",
            status=JobStatus.complete,
            source_key="jobs/media/source/job-3",
            result_key="jobs/media/result/job-3.png",
            source_content_type="image/png",
        )

        await service.get_result_url(job)

        storage_backend.presign_read.assert_awaited_once_with(
            "jobs/media/result/job-3.png",
            expires_in=3600,
        )
