from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TenantOnboardRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    slug: str = Field(..., min_length=2, max_length=50)
    subscription_plan: str = "ENTERPRISE"  # STARTER, PRO, ENTERPRISE
    contact_email: Optional[str] = None
    initial_admin_name: Optional[str] = None
    initial_admin_email: Optional[str] = None


class TenantDetailResponse(BaseModel):
    id: str
    name: str
    slug: str
    status: str  # ACTIVE, PENDING, SUSPENDED
    subscription_plan: str
    cinema_count: int
    created_at: str


class TenantStatusUpdateRequest(BaseModel):
    status: str  # ACTIVE, SUSPENDED
    reason: Optional[str] = None


class PlatformAnalyticsResponse(BaseModel):
    total_tenants: int
    active_cinemas: int
    total_bookings: int
    gross_volume_minor: int
    currency: str
    average_occupancy_percentage: float
    system_health: str


class AuditLogResponse(BaseModel):
    id: str
    action: str
    performed_by: str
    entity_type: str
    entity_id: str
    details: Dict[str, Any]
    timestamp: str
