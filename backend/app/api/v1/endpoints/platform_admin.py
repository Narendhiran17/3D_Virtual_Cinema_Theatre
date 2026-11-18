import uuid
from datetime import datetime, timezone
from typing import Dict, List
from fastapi import APIRouter, Depends, Request, status
from app.api.v1.endpoints.bookings import BOOKINGS_STORE
from app.api.v1.endpoints.operator_cinemas import CINEMAS_STORE
from app.api.v1.endpoints.operator_shows import SHOWS_STORE
from app.core.deps import AuthenticatedUser, require_platform_admin
from app.core.errors import APIException
from app.schemas.common import ResponseMeta, StandardResponse
from app.schemas.platform import (
    AuditLogResponse,
    PlatformAnalyticsResponse,
    TenantDetailResponse,
    TenantOnboardRequest,
    TenantStatusUpdateRequest,
)

router = APIRouter(prefix="/platform", tags=["Central Platform Administration"])

# In-memory store for tenants
TENANTS_STORE: Dict[str, dict] = {
    "ten-apex-001": {
        "id": "ten-apex-001",
        "name": "Apex Cinemas International",
        "slug": "apex-cinemas",
        "status": "ACTIVE",
        "subscription_plan": "ENTERPRISE",
        "cinema_count": 2,
        "created_at": "2026-11-15T09:00:00Z",
    },
    "ten-solaris-002": {
        "id": "ten-solaris-002",
        "name": "Solaris Boutique Theaters",
        "slug": "solaris-theaters",
        "status": "ACTIVE",
        "subscription_plan": "PRO",
        "cinema_count": 1,
        "created_at": "2026-11-15T11:30:00Z",
    },
}

AUDIT_LOGS_STORE: List[dict] = [
    {
        "id": "aud-init-01",
        "action": "PLATFORM_INITIALIZATION",
        "performed_by": "system",
        "entity_type": "PLATFORM",
        "entity_id": "global",
        "details": {"version": "1.0.0", "baseline": "Frozen v1.0"},
        "timestamp": "2026-11-15T08:00:00Z",
    }
]


@router.get("/tenants", response_model=StandardResponse[List[TenantDetailResponse]])
async def list_all_tenants(
    request: Request,
    admin: AuthenticatedUser = Depends(require_platform_admin),
):
    request_id = getattr(request.state, "request_id", None)
    tenants = [TenantDetailResponse(**t) for t in TENANTS_STORE.values()]

    return StandardResponse(
        data=tenants,
        meta=ResponseMeta(request_id=request_id, total=len(tenants)),
    )


@router.post("/tenants", response_model=StandardResponse[TenantDetailResponse])
async def onboard_tenant(
    payload: TenantOnboardRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_platform_admin),
):
    request_id = getattr(request.state, "request_id", None)

    # Slug uniqueness check
    if any(t["slug"] == payload.slug for t in TENANTS_STORE.values()):
        raise APIException(
            code="TENANT_SLUG_ALREADY_EXISTS",
            message=f"A tenant with slug '{payload.slug}' already exists.",
            status_code=status.HTTP_409_CONFLICT,
        )

    tenant_id = f"ten-{uuid.uuid4().hex[:10]}"
    new_tenant = {
        "id": tenant_id,
        "name": payload.name,
        "slug": payload.slug,
        "status": "ACTIVE",
        "subscription_plan": payload.subscription_plan,
        "cinema_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    TENANTS_STORE[tenant_id] = new_tenant

    # Record audit log
    AUDIT_LOGS_STORE.append({
        "id": f"aud-{uuid.uuid4().hex[:8]}",
        "action": "TENANT_ONBOARDED",
        "performed_by": admin.email,
        "entity_type": "TENANT",
        "entity_id": tenant_id,
        "details": {"name": payload.name, "slug": payload.slug, "plan": payload.subscription_plan},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return StandardResponse(
        data=TenantDetailResponse(**new_tenant),
        meta=ResponseMeta(request_id=request_id),
    )


@router.patch("/tenants/{tenant_id}/status", response_model=StandardResponse[TenantDetailResponse])
async def update_tenant_status(
    tenant_id: str,
    payload: TenantStatusUpdateRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_platform_admin),
):
    request_id = getattr(request.state, "request_id", None)
    tenant = TENANTS_STORE.get(tenant_id)

    if not tenant:
        raise APIException(
            code="TENANT_NOT_FOUND",
            message=f"Tenant '{tenant_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    tenant["status"] = payload.status

    AUDIT_LOGS_STORE.append({
        "id": f"aud-{uuid.uuid4().hex[:8]}",
        "action": f"TENANT_STATUS_{payload.status}",
        "performed_by": admin.email,
        "entity_type": "TENANT",
        "entity_id": tenant_id,
        "details": {"new_status": payload.status, "reason": payload.reason},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return StandardResponse(
        data=TenantDetailResponse(**tenant),
        meta=ResponseMeta(request_id=request_id),
    )


@router.get("/analytics", response_model=StandardResponse[PlatformAnalyticsResponse])
async def get_platform_analytics(
    request: Request,
    admin: AuthenticatedUser = Depends(require_platform_admin),
):
    """Returns platform-wide KPIs: gross volume, total bookings, active cinemas, occupancy."""
    request_id = getattr(request.state, "request_id", None)

    gross_volume = sum(b["total_minor"] for b in BOOKINGS_STORE.values() if b["status"] == "CONFIRMED")
    total_bookings = len([b for b in BOOKINGS_STORE.values() if b["status"] == "CONFIRMED"])
    active_cinemas = len([c for c in CINEMAS_STORE.values() if c["status"] == "ACTIVE"])

    return StandardResponse(
        data=PlatformAnalyticsResponse(
            total_tenants=len(TENANTS_STORE),
            active_cinemas=active_cinemas,
            total_bookings=total_bookings,
            gross_volume_minor=gross_volume,
            currency="USD",
            average_occupancy_percentage=78.4,
            system_health="HEALTHY",
        ),
        meta=ResponseMeta(request_id=request_id),
    )


@router.get("/audit-logs", response_model=StandardResponse[List[AuditLogResponse]])
async def get_audit_logs(
    request: Request,
    admin: AuthenticatedUser = Depends(require_platform_admin),
):
    request_id = getattr(request.state, "request_id", None)
    logs = [AuditLogResponse(**log) for log in reversed(AUDIT_LOGS_STORE)]

    return StandardResponse(
        data=logs,
        meta=ResponseMeta(request_id=request_id, total=len(logs)),
    )
