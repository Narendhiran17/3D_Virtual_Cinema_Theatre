from typing import List
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from app.core.deps import get_current_tenant_id
from app.schemas.common import StandardResponse, ResponseMeta

router = APIRouter(prefix="/cinemas", tags=["Cinemas Discovery"])


class CinemaSummary(BaseModel):
    id: str
    tenant_id: str
    name: str
    city: str
    country_code: str
    timezone: str
    status: str


class CreateCinemaRequest(BaseModel):
    name: str
    city: str
    country_code: str
    timezone: str


@router.get("", response_model=StandardResponse[List[CinemaSummary]])
async def list_cinemas(request: Request, city: str = None):
    request_id = getattr(request.state, "request_id", None)
    # Baseline discovery stub
    sample_cinemas = [
        CinemaSummary(
            id="cin-1001-a1b2-c3d4",
            tenant_id="ten-apex-001",
            name="Apex Grand Cinema - IMAX & 3D",
            city="Metropolis",
            country_code="US",
            timezone="America/New_York",
            status="ACTIVE",
        )
    ]
    return StandardResponse(
        data=sample_cinemas,
        meta=ResponseMeta(request_id=request_id, total=len(sample_cinemas)),
    )


@router.post("", response_model=StandardResponse[CinemaSummary])
async def create_cinema(
    payload: CreateCinemaRequest,
    request: Request,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Protected operator endpoint enforcing tenant isolation."""
    request_id = getattr(request.state, "request_id", None)
    new_cinema = CinemaSummary(
        id="cin-2002-x1y2-z3w4",
        tenant_id=tenant_id,
        name=payload.name,
        city=payload.city,
        country_code=payload.country_code,
        timezone=payload.timezone,
        status="ACTIVE",
    )
    return StandardResponse(
        data=new_cinema,
        meta=ResponseMeta(request_id=request_id),
    )

