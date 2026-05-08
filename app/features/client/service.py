from io import BytesIO
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.core.config import environment, logger
from app.core.queue import QueueName
from app.features.client.enums import (
    ALLOWED_IMAGE_CONTENT_TYPES,
    MAX_IMAGE_DIMENSION,
)
from app.features.client.schemas import RembgJobQueuedResponse, RembgJobResponse
from app.features.rembg.enums import REMBG_JOB_NAME
from app.features.storage import RembgJobStatus, RembgStorageService


class RembgClientService:
    def __init__(
        self,
        storage: RembgStorageService,
        queue_pool: Any,
    ) -> None:
        self.storage = storage
        self.queue_pool = queue_pool

    async def create_job(self, upload: UploadFile) -> RembgJobQueuedResponse:
        image_bytes = await upload.read()
        content_type = self._validate_upload(image_bytes, upload.content_type)

        job = self.storage.build_job(
            job_id=str(uuid4()),
            source_content_type=content_type,
            source_filename=upload.filename,
        )

        await self.storage.upload_source(job, image_bytes)
        await self.storage.save_job(job)

        try:
            await self.queue_pool.enqueue_job(
                REMBG_JOB_NAME,
                job.job_id,
                _queue_name=QueueName.compute,
            )
        except Exception as exc:
            await self.storage.delete_job(job.job_id)
            await self.storage.delete_source(job)
            logger.exception("Failed to enqueue rembg job", job_id=job.job_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to enqueue background removal job",
            ) from exc

        return RembgJobQueuedResponse(job_id=job.job_id, status=job.status)

    async def get_job_response(self, job_id: str) -> RembgJobResponse | None:
        job = await self.storage.get_job(job_id)
        if job is None:
            return None

        result_url = None
        if job.status == RembgJobStatus.complete:
            result_url = await self.storage.get_result_url(job)

        return RembgJobResponse(
            job_id=job.job_id,
            status=job.status,
            result_url=result_url,
            error=job.error,
            attempts=job.attempts,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    async def require_job_response(self, job_id: str) -> RembgJobResponse:
        payload = await self.get_job_response(job_id)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )
        return payload

    def _validate_upload(self, image_bytes: bytes, content_type: str | None) -> str:
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upload is empty",
            )

        if len(image_bytes) > environment.MAX_BODY_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Upload exceeds the maximum allowed size",
            )

        try:
            with Image.open(BytesIO(image_bytes)) as image:
                width, height = image.size
                detected_content_type = (
                    Image.MIME.get(image.format, "").lower() if image.format else None
                )
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upload must be a valid PNG, JPEG, or WEBP image",
            ) from exc

        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Image dimensions must be at most "
                    f"{MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}px"
                ),
            )

        normalized_content_type = self._normalize_content_type(
            content_type,
            detected_content_type,
        )
        if normalized_content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PNG, JPEG, and WEBP images are supported",
            )

        return normalized_content_type

    @staticmethod
    def _normalize_content_type(
        content_type: str | None,
        detected_content_type: str | None,
    ) -> str:
        candidates: list[str] = []
        if content_type:
            normalized_content_type = content_type.lower().strip()
            if normalized_content_type == "image/jpg":
                normalized_content_type = "image/jpeg"
            candidates.append(normalized_content_type)

        if detected_content_type:
            candidates.append(detected_content_type)

        for candidate in candidates:
            if candidate in ALLOWED_IMAGE_CONTENT_TYPES:
                return candidate

        return ""
