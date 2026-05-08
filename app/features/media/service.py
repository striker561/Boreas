from io import BytesIO
from contextlib import suppress
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import ValidationError

from app.core.config import environment, logger
from app.core.queue import QueueName
from app.core.storage import JobStatus, MediaStorageService
from app.features.media.enums import (
    ALLOWED_IMAGE_CONTENT_TYPES,
    INGEST_MEDIA_JOB_NAME,
    MAX_IMAGE_DIMENSION,
)
from app.features.media.schemas import (
    MediaJobQueuedResponse,
    MediaJobResponse,
    MediaUploadInspection,
    NormalizedMediaUpload,
    StagedMediaUpload,
    StagedUploadMetadata,
)
from app.features.rembg.enums import REMOVE_BACKGROUND_JOB_NAME

UPLOAD_READ_CHUNK_SIZE = 1024 * 1024


class MediaService:
    def __init__(
        self,
        storage: MediaStorageService,
        queue_pool: Any,
    ) -> None:
        self.storage = storage
        self.queue_pool = queue_pool

    async def create_job(self, upload: UploadFile) -> MediaJobQueuedResponse:
        job = None
        try:
            image_bytes = await self._read_upload_bytes(upload)
            inspection = self._inspect_upload(
                image_bytes=image_bytes,
                content_type=upload.content_type,
                filename=upload.filename,
                raise_http=True,
            )
            staged_upload_metadata = self._build_staged_upload_metadata(inspection)

            job = self.storage.build_job(
                job_id=str(uuid4()),
                source_content_type=inspection.content_type,
                source_filename=upload.filename,
                source_size_bytes=inspection.size_bytes,
            )

            await self.storage.save_job(job)
            await self.storage.save_staged_upload(
                job.job_id,
                payload=image_bytes,
                metadata=staged_upload_metadata.model_dump(mode="json"),
            )
            await self.queue_pool.enqueue_job(
                INGEST_MEDIA_JOB_NAME,
                job.job_id,
                _queue_name=QueueName.media,
            )
            logger.info(
                "Media job queued",
                job_id=job.job_id,
                content_type=inspection.content_type,
                size_bytes=inspection.size_bytes,
            )
        except HTTPException:
            raise
        except Exception as exc:
            if job is not None:
                await self.storage.delete_staged_upload(job.job_id)
                await self.storage.delete_job(job.job_id)
            logger.exception(
                "Failed to enqueue media job",
                job_id=job.job_id if job is not None else None,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to enqueue media job",
            ) from exc
        finally:
            with suppress(Exception):
                await upload.close()

        return MediaJobQueuedResponse(job_id=job.job_id, status=job.status)

    async def ingest_job(self, job_id: str) -> None:
        job = await self.storage.get_job(job_id)
        if job is None:
            logger.warning("Media job missing in Redis", job_id=job_id)
            return

        if await self.storage.result_exists(job):
            job.mark_complete()
            await self.storage.save_job(job)
            await self.storage.delete_staged_upload(job.job_id)
            if await self.storage.source_exists(job):
                await self.storage.delete_source(job)
            return

        if await self.storage.source_exists(job):
            await self.storage.delete_staged_upload(job.job_id)
            await self.queue_pool.enqueue_job(
                REMOVE_BACKGROUND_JOB_NAME,
                job.job_id,
                _queue_name=QueueName.compute,
            )
            return

        staged_upload_metadata = await self.storage.get_staged_upload_metadata(
            job.job_id
        )
        staged_upload_payload = await self.storage.get_staged_upload_payload(job.job_id)
        if staged_upload_metadata is None or staged_upload_payload is None:
            await self.fail_job(job_id, "Queued upload expired before ingestion")
            return

        try:
            staged_upload = StagedMediaUpload.model_validate(
                {
                    **staged_upload_metadata,
                    "payload": staged_upload_payload,
                }
            )
        except ValidationError as exc:
            await self.fail_job(job_id, self._format_validation_error(exc))
            return

        job.mark_preparing()
        await self.storage.save_job(job)

        try:
            normalized_upload = self._normalize_source_upload(
                staged_upload=staged_upload,
            )
        except (ValidationError, ValueError) as exc:
            await self.fail_job(job_id, self._format_validation_error(exc))
            return

        await self.storage.upload_source(
            job,
            normalized_upload.payload,
            content_type=normalized_upload.content_type,
        )
        logger.info(
            "Prepared source uploaded",
            job_id=job.job_id,
            source_size_bytes=normalized_upload.size_bytes,
            content_type=normalized_upload.content_type,
        )

        job.source_content_type = normalized_upload.content_type
        job.source_size_bytes = normalized_upload.size_bytes
        await self.storage.save_job(job)
        await self.storage.delete_staged_upload(job.job_id)

        await self.queue_pool.enqueue_job(
            REMOVE_BACKGROUND_JOB_NAME,
            job.job_id,
            _queue_name=QueueName.compute,
        )

    async def get_job_response(self, job_id: str) -> MediaJobResponse | None:
        job = await self.storage.get_job(job_id)
        if job is None:
            return None

        result_url = None
        if job.status == JobStatus.complete:
            result_url = await self.storage.get_result_url(job)

        return MediaJobResponse(
            job_id=job.job_id,
            status=job.status,
            result_url=result_url,
            error=job.error,
            attempts=job.attempts,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    async def require_job_response(self, job_id: str) -> MediaJobResponse:
        payload = await self.get_job_response(job_id)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )
        return payload

    async def fail_job(self, job_id: str, error: str) -> None:
        job = await self.storage.get_job(job_id)
        if job is None:
            return

        await self.storage.delete_staged_upload(job_id)
        job.mark_failed(error)
        await self.storage.save_job(job)
        logger.warning("Media job failed", job_id=job_id, error=error)

    @staticmethod
    def _build_staged_upload_metadata(
        inspection: MediaUploadInspection,
    ) -> StagedUploadMetadata:
        return StagedUploadMetadata.model_validate(
            {
                "filename": inspection.filename,
                "content_type": inspection.content_type,
                "size_bytes": inspection.size_bytes,
                "width": inspection.width,
                "height": inspection.height,
            }
        )

    @staticmethod
    async def _read_upload_bytes(upload: UploadFile) -> bytes:
        total_size = 0
        chunks = bytearray()

        while True:
            chunk = await upload.read(UPLOAD_READ_CHUNK_SIZE)
            if not chunk:
                return bytes(chunks)

            total_size += len(chunk)
            if total_size > environment.MAX_BODY_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Upload exceeds the maximum request size",
                )

            chunks.extend(chunk)

    def _inspect_upload(
        self,
        image_bytes: bytes,
        content_type: str | None,
        filename: str | None,
        *,
        raise_http: bool,
    ) -> MediaUploadInspection:
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upload is empty",
            )

        try:
            with Image.open(BytesIO(image_bytes)) as image:
                width, height = image.size
                detected_content_type = (
                    Image.MIME.get(image.format, "").lower() if image.format else None
                )
        except (UnidentifiedImageError, OSError) as exc:
            if raise_http:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Upload must be a valid PNG, JPEG, or WEBP image",
                ) from exc
            raise ValueError("Upload must be a valid PNG, JPEG, or WEBP image") from exc

        try:
            return MediaUploadInspection.model_validate(
                {
                    "filename": filename,
                    "content_type": self._normalize_content_type(
                        content_type,
                        detected_content_type,
                    ),
                    "size_bytes": len(image_bytes),
                    "width": width,
                    "height": height,
                }
            )
        except ValidationError as exc:
            if raise_http:
                raise self._http_exception_from_validation(exc) from exc
            raise

    def _normalize_source_upload(
        self,
        staged_upload: StagedMediaUpload,
    ) -> NormalizedMediaUpload:
        if staged_upload.size_bytes <= environment.MEDIA_SOURCE_MAX_BYTES:
            return NormalizedMediaUpload.model_validate(
                {
                    "payload": staged_upload.payload,
                    "content_type": staged_upload.content_type,
                    "size_bytes": staged_upload.size_bytes,
                    "width": staged_upload.width,
                    "height": staged_upload.height,
                }
            )

        with Image.open(BytesIO(staged_upload.payload)) as image:
            prepared_image = ImageOps.exif_transpose(image).copy()

        return self._compress_to_source_limit(prepared_image)

    def _compress_to_source_limit(self, image: Image.Image) -> NormalizedMediaUpload:
        has_alpha = self._has_alpha(image)
        scales = (1.0, 0.92, 0.84, 0.76, 0.68, 0.6)

        for scale in scales:
            candidate = image if scale == 1.0 else self._resize_image(image, scale)
            for payload, content_type in self._encode_candidates(candidate, has_alpha):
                try:
                    return NormalizedMediaUpload.model_validate(
                        {
                            "payload": payload,
                            "content_type": content_type,
                            "size_bytes": len(payload),
                            "width": candidate.width,
                            "height": candidate.height,
                        }
                    )
                except ValidationError:
                    continue

        raise ValueError("Unable to fit image within the 2 MB media limit")

    def _encode_candidates(
        self,
        image: Image.Image,
        has_alpha: bool,
    ) -> list[tuple[bytes, str]]:
        candidates: list[tuple[bytes, str]] = []

        if has_alpha:
            for quality in (90, 82, 74, 66):
                candidates.append(
                    (
                        self._save_image(image, "WEBP", quality=quality),
                        "image/webp",
                    )
                )
            candidates.append((self._save_image(image, "PNG"), "image/png"))
            return candidates

        for quality in (88, 80, 72, 64):
            candidates.append(
                (
                    self._save_image(image, "JPEG", quality=quality),
                    "image/jpeg",
                )
            )
        for quality in (86, 78, 70):
            candidates.append(
                (
                    self._save_image(image, "WEBP", quality=quality),
                    "image/webp",
                )
            )
        candidates.append((self._save_image(image, "PNG"), "image/png"))
        return candidates

    def _save_image(
        self,
        image: Image.Image,
        image_format: str,
        *,
        quality: int | None = None,
    ) -> bytes:
        output = BytesIO()

        if image_format == "JPEG":
            image.convert("RGB").save(
                output,
                format=image_format,
                optimize=True,
                quality=quality or 82,
                progressive=True,
            )
            return output.getvalue()

        if image_format == "WEBP":
            image.save(
                output,
                format=image_format,
                quality=quality or 80,
                method=6,
            )
            return output.getvalue()

        image.save(output, format=image_format, optimize=True, compress_level=9)
        return output.getvalue()

    @staticmethod
    def _resize_image(image: Image.Image, scale: float) -> Image.Image:
        width = max(1, int(image.width * scale))
        height = max(1, int(image.height * scale))
        return image.resize((width, height), Image.Resampling.LANCZOS)

    @staticmethod
    def _has_alpha(image: Image.Image) -> bool:
        if image.mode in {"RGBA", "LA"}:
            return True
        if image.mode == "P" and "transparency" in image.info:
            return True
        return False

    @staticmethod
    def _format_validation_error(exc: ValidationError | ValueError) -> str:
        if isinstance(exc, ValidationError):
            if not exc.errors():
                return "Invalid media payload"

            return MediaService._normalize_validation_message(exc.errors()[0]["msg"])

        return MediaService._normalize_validation_message(str(exc))

    @staticmethod
    def _normalize_validation_message(message: str) -> str:
        normalized_message = message.removeprefix("Value error, ").strip()

        if "Image dimensions must be at most" in normalized_message:
            return (
                f"{normalized_message}. This limit protects worker memory and processing time. "
                "Resize the image and try again."
            )

        if normalized_message == "Upload exceeds the maximum request size":
            return (
                f"{normalized_message}. Maximum allowed request size is "
                f"{environment.MAX_BODY_SIZE // (1024 * 1024)} MB."
            )

        return normalized_message

    def _http_exception_from_validation(self, exc: ValidationError) -> HTTPException:
        message = self._format_validation_error(exc)
        status_code = (
            status.HTTP_413_CONTENT_TOO_LARGE
            if "maximum request size" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        return HTTPException(status_code=status_code, detail=message)

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
