from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

from app.core.config import environment, logger
from app.core.middleware import (
    BodySizeLimitMiddleware,
    LogMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    TrustedHostMiddleware,
)
from app.core.queue import close_arq_pool, get_arq_pool
from app.core.rate_limit import limiter
from app.core.storage.dependency import get_redis_cache
from app.helpers import APIResponse, format_validation_errors


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    redis_cache = get_redis_cache()

    await redis_cache.connect()
    await get_arq_pool()  # warm up arq connection on startup

    try:
        yield
    finally:
        await redis_cache.disconnect()
        await close_arq_pool()


app = FastAPI(
    debug=not environment.IS_PRODUCTION,
    title=environment.APP_NAME,
    version=environment.APP_VERSION,
    lifespan=lifespan,
    docs_url=None if environment.IS_PRODUCTION else "/docs",
    redoc_url=None if environment.IS_PRODUCTION else "/redoc",
)

# Add SlowAPI state
app.state.limiter = limiter

# Middlewares added last run first (LIFO stack)

# Add SlowAPI middleware (8)
app.add_middleware(SlowAPIMiddleware)

# Request body size limit (7)
app.add_middleware(
    BodySizeLimitMiddleware,
    max_body_size=environment.MAX_BODY_SIZE,
)
# Request Logging (6)
app.add_middleware(
    LogMiddleware,
)
# Request ID tracking (5)
app.add_middleware(
    RequestIDMiddleware,
)
# Security middleware (4)
app.add_middleware(
    SecurityHeadersMiddleware,
)
# Trusted MiddleWare (3)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=environment.trusted_hosts_list,
)
# Response compression (2)
app.add_middleware(
    GZipMiddleware,
    minimum_size=environment.GZIP_MIN_SIZE,
)
# CORS setup (1)
app.add_middleware(
    CORSMiddleware,
    allow_origins=environment.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Handle SlowAPI rate limit exceeded exceptions."""
    return APIResponse.error(
        msg="Too many requests. Please slow down and try again later.",
        status=429,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI request validation errors (422) in APIResponse format."""
    return APIResponse.validation(
        errors=format_validation_errors(exc.errors()),
        msg="Validation failed",
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle HTTP exceptions raised by FastAPI and Starlette."""
    message = str(exc.detail) if exc.detail else "Request failed"
    response = APIResponse.error(
        msg=message,
        status=exc.status_code,
    )
    if exc.headers:
        response.headers.update(exc.headers)
    return response


@app.exception_handler(ValidationError)
async def validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    return APIResponse.validation(
        errors=format_validation_errors(exc.errors()),
        msg="Validation failed",
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.error("Unhandled exception", error=str(exc), exc_info=True)
    return APIResponse.server_error(
        msg="An unexpected error occurred",
    )
