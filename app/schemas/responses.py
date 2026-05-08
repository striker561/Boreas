from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIResponseSchema[T](BaseModel):
    """Standard success response envelope for OpenAPI docs.

    Usage:
        response_model=APIResponseSchema[SomeSchema]

    Shape:
        {"msg": "...", "data": ...}
    """

    model_config = ConfigDict(from_attributes=True)

    msg: str = Field(default="Success", examples=["Success"])
    data: T | None = None


class APIErrorResponseSchema(BaseModel):
    """Standard error response envelope for OpenAPI docs.

    Shape:
        {"msg": "...", "errors": [...] | {...}}
    """

    msg: str = Field(default="Something went wrong", examples=["Something went wrong"])
    errors: dict[str, Any] | list[Any] = Field(default_factory=list)
