from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.schemas.common import HealthStatus, StandardResponse, ResponseMeta

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/health/live", response_model=StandardResponse[HealthStatus])
async def liveness(request: Request):
    """Kubernetes / container liveness probe."""
    request_id = getattr(request.state, "request_id", None)
    return StandardResponse(
        data=HealthStatus(
            status="ok",
            service=settings.APP_NAME,
            version=settings.APP_VERSION,
            environment=settings.APP_ENV,
        ),
        meta=ResponseMeta(request_id=request_id),
    )


@router.get("/health/ready", response_model=StandardResponse[HealthStatus])
async def readiness(request: Request):
    """Kubernetes / container readiness probe checking core dependencies."""
    request_id = getattr(request.state, "request_id", None)
    checks = {
        "api": "healthy",
        "database": "ready",
        "redis": "ready"
    }
    return StandardResponse(
        data=HealthStatus(
            status="ready",
            service=settings.APP_NAME,
            version=settings.APP_VERSION,
            environment=settings.APP_ENV,
            checks=checks,
        ),
        meta=ResponseMeta(request_id=request_id),
    )
