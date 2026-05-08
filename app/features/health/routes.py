from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.features.health.schemas import HealthReport, HealthStatusPayload
from app.helpers import APIResponse
from app.schemas import APIResponseSchema
from app.features.health.service import HealthService, build_health_service

router = APIRouter(tags=["Status"])


@router.get(
    "/",
    response_model=APIResponseSchema[HealthStatusPayload],
    summary="Get application status",
    description="Lightweight reachability endpoint intended for simple uptime checks.",
)
async def status_check() -> JSONResponse:
    return APIResponse.success(
        msg="Application healthy",
        data=HealthStatusPayload(),
    )


@router.get(
    "/health",
    response_model=APIResponseSchema[HealthReport],
    summary="Get operational health report",
    description=(
        "Return public operational metrics for Boreas, including dependency reachability, "
        "queue depth, staged uploads, worker counts, and key runtime limits."
    ),
    responses={
        503: {
            "description": "The API is reachable, but one or more dependencies are degraded.",
        }
    },
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
