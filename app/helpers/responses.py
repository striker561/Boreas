from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


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
    def server_error(msg: str = "Internal server error") -> JSONResponse:
        return APIResponse.error(msg=msg, status=500)
