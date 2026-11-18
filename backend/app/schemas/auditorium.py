from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuditoriumCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    capacity: int = Field(..., gt=0)
    auditorium_type: str = "IMAX_3D"  # IMAX_3D, DOLBY_ATMOS, STANDARD


class AuditoriumResponse(BaseModel):
    id: str
    tenant_id: str
    cinema_id: str
    name: str
    capacity: int
    auditorium_type: str
    status: str
    active_layout_version: Optional[int] = 1


class ScreenMetadataSchema(BaseModel):
    width: float = 16.0
    height: float = 7.0
    curve_radius: Optional[float] = 24.0
    center: List[float] = [0.0, 4.5, -14.0]
    normal: List[float] = [0.0, 0.0, 1.0]


class SeatDefinitionSchema(BaseModel):
    row_label: str
    seat_number: str
    seat_type: str = "STANDARD"  # STANDARD, PREMIUM, RECLINER, ACCESSIBLE
    position_x: float
    position_y: float
    position_z: float
    object_identifier: str  # e.g., "SEAT_A_05"


class LayoutPublishRequest(BaseModel):
    geometry_metadata: Dict[str, Any] = {
        "dimensions": {"width": 18.0, "length": 22.0, "slope_degrees": 8.5}
    }
    screen_configuration: ScreenMetadataSchema = ScreenMetadataSchema()
    seats: List[SeatDefinitionSchema]


class LayoutSeatItem(BaseModel):
    seat_id: str
    label: str
    row: str
    number: str
    seat_type: str
    position: List[float]
    eye_point: List[float]
    object_identifier: str


class AuditoriumLayoutResponse(BaseModel):
    layout_id: str
    auditorium_id: str
    version: int
    status: str
    screen: ScreenMetadataSchema
    geometry_metadata: Dict[str, Any]
    seats: List[LayoutSeatItem]
    published_at: Optional[str] = None
