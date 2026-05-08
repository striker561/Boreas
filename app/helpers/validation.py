from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def format_validation_errors(
    errors: Sequence[Mapping[str, Any]],
) -> list[dict[str, object]]:
    """Normalize pydantic/FastAPI validation errors into a stable API shape.

    Output shape:
        [{"loc": "body.password", "msg": "...", "type": "value_error"}, ...]

    This keeps frontend error handling predictable across FastAPI/Pydantic versions.
    """

    formatted: list[dict[str, object]] = []
    for error in errors:
        loc = ".".join(str(x) for x in error.get("loc", ()))
        formatted.append(
            {
                "loc": loc,
                "msg": error.get("msg", "Invalid value"),
                "type": error.get("type", "validation_error"),
            }
        )
    return formatted
