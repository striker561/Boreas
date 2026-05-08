from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.helpers import APIResponse
from app.schemas import APIResponseSchema

from app.features.health.service import HealthService, build_health_service

router = APIRouter(tags=["Status"])


@router.get(
    "/",
    response_model=APIResponseSchema,
)
async def status_check(
    service: HealthService = Depends(build_health_service),
) -> JSONResponse:
    return APIResponse.success(
        msg="Application healthy",
        data=await service.get_status(),
    )


@router.get(
    "/health",
    response_model=APIResponseSchema,
)
async def public_health(
    service: HealthService = Depends(build_health_service),
) -> JSONResponse:
    status_code, data = await service.get_health()
    return APIResponse.success(
        msg="Application health",
        data=data,
        status=status_code,
    )
