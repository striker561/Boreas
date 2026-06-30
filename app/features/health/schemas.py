from typing import Literal

from pydantic import BaseModel, Field


class HealthStatusPayload(BaseModel):
    status: Literal["ok"] = Field(
        default="ok",
        description="Lightweight application status used for quick reachability checks.",
    )


class HealthDependencyStatus(BaseModel):
    reachable: bool = Field(
        description="Whether the dependency responded successfully to its health probe.",
        examples=[True],
    )


class HealthWorkers(BaseModel):
    media: int = Field(description="Configured number of media ingest workers.")
    background_removal: int = Field(
        description="Configured number of background-removal workers."
    )


class HealthSseStreams(BaseModel):
    active_streams: int = Field(
        description="Open SSE job streams on this API process.",
        examples=[0],
    )
    tracked_jobs: int = Field(
        description="Distinct job ids with at least one SSE waiter on this process.",
        examples=[0],
    )
    listener_running: bool = Field(
        description="Whether the Redis pub/sub listener task is alive on this process.",
        examples=[True],
    )


class HealthLimits(BaseModel):
    api_rate_limit: str = Field(
        description="Configured moving-window rate limit for read-style API requests."
    )
    upload_rate_limit: str = Field(
        description="Configured moving-window rate limit for media uploads."
    )
    job_ttl_seconds: int = Field(
        description="Redis TTL applied to job metadata records."
    )
    result_url_ttl_seconds: int = Field(
        description="Lifetime of presigned result URLs in seconds."
    )
    media_source_max_bytes: int = Field(
        description="Maximum size of the normalized source object sent to compute workers."
    )


class HealthReport(BaseModel):
    status: Literal["ok", "degraded"] = Field(
        description="Overall service health derived from dependency reachability."
    )
    redis: HealthDependencyStatus
    arq: HealthDependencyStatus
    queue_depths: dict[str, int] = Field(
        description="Current queued job counts per ARQ queue.",
        examples=[{"boreas:media": 0, "boreas:compute": 0}],
    )
    staged_uploads: int = Field(
        description="Number of staged uploads currently waiting in Redis.",
        examples=[0],
    )
    sse_streams: HealthSseStreams = Field(
        description="In-process media job SSE hub metrics (per API worker, not cluster-wide).",
    )
    workers: HealthWorkers
    limits: HealthLimits
