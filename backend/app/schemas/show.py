from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ShowScheduleCreate(BaseModel):
    cinema_id: str
    auditorium_id: str
    movie_id: str
    starts_at: str  # ISO-8601 UTC
    ends_at: str    # ISO-8601 UTC
    timezone: str = "America/New_York"
    format: str = "IMAX_3D"
    pricing_overrides_minor: Optional[Dict[str, int]] = None  # e.g. {"STANDARD": 1800, "PREMIUM": 2500}


class ShowDetailResponse(BaseModel):
    id: str
    tenant_id: str
    cinema_id: str
    auditorium_id: str
    movie_id: str
    movie_title: str
    layout_version: int
    starts_at: str
    ends_at: str
    timezone: str
    format: str
    status: str
    total_seats: int
    available_seats: int
    created_at: Optional[str] = None


class ShowSeatInventoryItem(BaseModel):
    show_seat_id: str
    seat_id: str
    label: str
    row: str
    number: str
    seat_type: str
    price_minor: int
    currency: str
    status: str
    version: int
    position: List[float]
    eye_point: List[float]
    object_identifier: str


class ShowSeatMapResponse(BaseModel):
    show_id: str
    auditorium_id: str
    layout_version: int
    currency: str
    seats: List[ShowSeatInventoryItem]
