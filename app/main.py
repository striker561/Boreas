from fastapi.responses import JSONResponse

from app.core import app
from app.features.routes import feature_router
from app.helpers.responses import APIResponse
from app.schemas import APIResponseSchema


@app.get(
    "/",
    tags=["Status"],
    response_model=APIResponseSchema,
)
def status_check() -> JSONResponse:
    """Application status"""
    return APIResponse.success(
        msg="Application healthy",
        data={"status": "ok"},
    )


# Register all feature routers
app.include_router(feature_router)
