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
    job_id: str
    status: JobStatus


class MediaJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    result_url: str | None = None
    error: str | None = None
    attempts: int
    created_at: datetime
    updated_at: datetime
