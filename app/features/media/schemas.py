from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import environment
from app.core.storage import JobStatus
from app.features.media.enums import ALLOWED_IMAGE_CONTENT_TYPES, MAX_IMAGE_DIMENSION


class MediaUploadInspection(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    filename: str | None = Field(default=None, max_length=255)
    content_type: str
    size_bytes: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_constraints(self) -> "MediaUploadInspection":
        if self.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValueError("Only PNG, JPEG, and WEBP images are supported")
        if self.size_bytes > environment.MAX_BODY_SIZE:
            raise ValueError("Upload exceeds the maximum request size")
        if self.width > MAX_IMAGE_DIMENSION or self.height > MAX_IMAGE_DIMENSION:
            raise ValueError(
                f"Image dimensions must be at most {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}px"
            )
        return self


class StagedMediaUpload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    filename: str | None = Field(default=None, max_length=255)
    payload: bytes
    content_type: str
    size_bytes: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_constraints(self) -> "StagedMediaUpload":
        if self.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValueError("Queued media has an unsupported content type")
        if len(self.payload) != self.size_bytes:
            raise ValueError("Queued media size metadata is invalid")
        if self.size_bytes > environment.MAX_BODY_SIZE:
            raise ValueError("Queued media exceeds the maximum request size")
        if self.width > MAX_IMAGE_DIMENSION or self.height > MAX_IMAGE_DIMENSION:
            raise ValueError(
                f"Image dimensions must be at most {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}px"
            )
        return self


class StagedUploadMetadata(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    filename: str | None = Field(default=None, max_length=255)
    content_type: str
    size_bytes: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_constraints(self) -> "StagedUploadMetadata":
        if self.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValueError("Queued media metadata has an unsupported content type")
        if self.size_bytes > environment.MAX_BODY_SIZE:
            raise ValueError("Queued media metadata exceeds the maximum request size")
        if self.width > MAX_IMAGE_DIMENSION or self.height > MAX_IMAGE_DIMENSION:
            raise ValueError(
                f"Image dimensions must be at most {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}px"
            )
        return self


class NormalizedMediaUpload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    payload: bytes
    content_type: str
    size_bytes: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_constraints(self) -> "NormalizedMediaUpload":
        if self.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValueError("Normalized media has an unsupported content type")
        if len(self.payload) != self.size_bytes:
            raise ValueError("Normalized media size metadata is invalid")
        if self.size_bytes > environment.MEDIA_SOURCE_MAX_BYTES:
            raise ValueError("Normalized media exceeds the 2 MB media limit")
        if self.width > MAX_IMAGE_DIMENSION or self.height > MAX_IMAGE_DIMENSION:
            raise ValueError(
                f"Image dimensions must be at most {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}px"
            )
        return self


class MediaJobQueuedResponse(BaseModel):
    job_id: str = Field(
        description="Opaque identifier used to poll or stream the job state.",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    status: JobStatus = Field(
        description="Initial lifecycle state recorded when the job is queued.",
        examples=[JobStatus.queued],
    )


class MediaJobResponse(BaseModel):
    job_id: str = Field(
        description="Opaque identifier returned when the job was created.",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    status: JobStatus = Field(
        description="Current lifecycle state of the job.",
        examples=[JobStatus.processing],
    )
    result_url: str | None = Field(
        default=None,
        description="Short-lived URL for downloading the final PNG once the job is complete.",
        examples=[
            "https://example.r2.cloudflarestorage.com/jobs/media/result/job.png?..."
        ],
    )
    error: str | None = Field(
        default=None,
        description="Failure reason when the job reaches the failed state.",
        examples=["Upload exceeds the maximum request size"],
    )
    attempts: int = Field(
        description="How many processing attempts have been recorded for this job.",
        examples=[1],
    )
    created_at: datetime = Field(
        description="UTC timestamp when the job was created.",
    )
    updated_at: datetime = Field(
        description="UTC timestamp when the job state last changed.",
    )
