from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response


class APIResponse:
    @staticmethod
    def success(
        msg: str = "Success",
        data: Any = None,
        status: int = 200,
    ) -> JSONResponse:
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "msg": msg,
                    "data": data,
                }
            ),
            status_code=status,
        )

    @staticmethod
    def created(
        msg: str = "Resource created",
        data: Any = None,
    ) -> JSONResponse:
        return APIResponse.success(msg=msg, data=data, status=201)

    @staticmethod
    def no_content() -> Response:
        """HTTP 204 No Content response."""
        return Response(status_code=204)

    @staticmethod
    def error(
        msg: str = "Something went wrong",
        errors: dict[str, Any] | list[Any] | None = None,
        status: int = 400,
    ) -> JSONResponse:
        return JSONResponse(
            content={
                "msg": msg,
                "errors": errors if errors is not None else [],
            },
            status_code=status,
        )

    @staticmethod
    def unauthorized(msg: str = "Unauthorized") -> JSONResponse:
        return APIResponse.error(msg=msg, status=401)

    @staticmethod
    def forbidden(msg: str = "Forbidden") -> JSONResponse:
        return APIResponse.error(msg=msg, status=403)

    @staticmethod
    def not_found(msg: str = "Resource not found") -> JSONResponse:
        return APIResponse.error(msg=msg, status=404)

    @staticmethod
    def validation(
        errors: dict[str, Any] | list[Any],
        msg: str = "Validation failed",
    ) -> JSONResponse:
        return JSONResponse(
            content={
                "msg": msg,
                "errors": errors,
            },
            status_code=422,
        )

    @staticmethod
    def too_many_requests(msg: str = "Too many requests") -> JSONResponse:
        return APIResponse.error(msg=msg, status=429)

    @staticmethod
    def server_error(msg: str = "Internal server error") -> JSONResponse:
        return APIResponse.error(msg=msg, status=500)
