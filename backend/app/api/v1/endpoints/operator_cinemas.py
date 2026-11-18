import uuid
from datetime import datetime, timezone
from typing import Dict, List
from fastapi import APIRouter, Depends, Request, status
from app.core.deps import get_current_tenant_id
from app.core.errors import APIException
from app.schemas.auditorium import (
    AuditoriumCreate,
    AuditoriumLayoutResponse,
    AuditoriumResponse,
    LayoutPublishRequest,
    LayoutSeatItem,
)
from app.schemas.cinema import CinemaCreate, CinemaResponse
from app.schemas.common import ResponseMeta, StandardResponse

router = APIRouter(prefix="/operator", tags=["Operator Cinema & Auditorium Management"])

# In-memory store for Sprint 3
# Key: cinema_id -> cinema record
CINEMAS_STORE: Dict[str, dict] = {
    "cin-apex-001": {
        "id": "cin-apex-001",
        "tenant_id": "ten-apex-001",
        "name": "Apex Grand Cinema - Manhattan Flagship",
        "address": {"street": "120 Broadway", "city": "New York", "state": "NY", "postal_code": "10005", "country": "US"},
        "city": "New York",
        "country_code": "US",
        "timezone": "America/New_York",
        "status": "ACTIVE",
        "created_at": "2026-11-15T10:00:00Z",
    }
}

# Key: auditorium_id -> auditorium record
AUDITORIUMS_STORE: Dict[str, dict] = {
    "aud-apex-imax-01": {
        "id": "aud-apex-imax-01",
        "tenant_id": "ten-apex-001",
        "cinema_id": "cin-apex-001",
        "name": "Auditorium 1 - IMAX Laser & 3D",
        "capacity": 50,
        "auditorium_type": "IMAX_3D",
        "status": "ACTIVE",
        "active_layout_version": 1,
    }
}

# Key: layout_id -> layout record
LAYOUTS_STORE: Dict[str, dict] = {}


def _generate_default_layout(auditorium_id: str, tenant_id: str) -> dict:
    rows = ["A", "B", "C", "D", "E"]
    cols = range(1, 11)
    seats: List[dict] = []

    for rIdx, row in enumerate(rows):
        z = -4.0 + rIdx * 2.2
        y = 0.8 + rIdx * 0.45
        seat_type = "PREMIUM" if row in ["D", "E"] else "STANDARD"

        for num in cols:
            aisle_offset = 0.6 if num > 5 else -0.6
            x = (num - 5.5) * 1.05 + aisle_offset
            label = f"{row}{num}"
            seat_id = f"seat-{auditorium_id}-{label.lower()}"
            obj_id = f"SEAT_{row}_{num:02d}"

            seats.append({
                "seat_id": seat_id,
                "label": label,
                "row": row,
                "number": str(num),
                "seat_type": seat_type,
                "position": [round(x, 3), round(y, 3), round(z, 3)],
                "eye_point": [round(x, 3), round(y + 1.1, 3), round(z, 3)],
                "object_identifier": obj_id,
            })

    return {
        "layout_id": f"lay-{auditorium_id}-v1",
        "auditorium_id": auditorium_id,
        "tenant_id": tenant_id,
        "version": 1,
        "status": "PUBLISHED",
        "screen": {
            "width": 16.0,
            "height": 7.0,
            "curve_radius": 24.0,
            "center": [0.0, 4.5, -14.0],
            "normal": [0.0, 0.0, 1.0],
        },
        "geometry_metadata": {
            "dimensions": {"width": 18.0, "length": 22.0, "slope_degrees": 8.5}
        },
        "seats": seats,
        "published_at": "2026-11-15T12:00:00Z",
    }


# Seed default layout
LAYOUTS_STORE["lay-aud-apex-imax-01-v1"] = _generate_default_layout("aud-apex-imax-01", "ten-apex-001")


@router.post("/cinemas", response_model=StandardResponse[CinemaResponse])
async def create_operator_cinema(
    payload: CinemaCreate,
    request: Request,
    tenant_id: str = Depends(get_current_tenant_id),
):
    request_id = getattr(request.state, "request_id", None)
    cinema_id = f"cin-{uuid.uuid4().hex[:12]}"

    cinema_record = {
        "id": cinema_id,
        "tenant_id": tenant_id,
        "name": payload.name,
        "address": payload.address.model_dump(),
        "city": payload.city,
        "country_code": payload.country_code,
        "timezone": payload.timezone,
        "status": "ACTIVE",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    CINEMAS_STORE[cinema_id] = cinema_record

    return StandardResponse(
        data=CinemaResponse(**cinema_record),
        meta=ResponseMeta(request_id=request_id),
    )


@router.get("/cinemas", response_model=StandardResponse[List[CinemaResponse]])
async def list_operator_cinemas(
    request: Request,
    tenant_id: str = Depends(get_current_tenant_id),
):
    request_id = getattr(request.state, "request_id", None)
    cinemas = [CinemaResponse(**c) for c in CINEMAS_STORE.values() if c["tenant_id"] == tenant_id]

    return StandardResponse(
        data=cinemas,
        meta=ResponseMeta(request_id=request_id, total=len(cinemas)),
    )


@router.post("/cinemas/{cinema_id}/auditoriums", response_model=StandardResponse[AuditoriumResponse])
async def create_cinema_auditorium(
    cinema_id: str,
    payload: AuditoriumCreate,
    request: Request,
    tenant_id: str = Depends(get_current_tenant_id),
):
    request_id = getattr(request.state, "request_id", None)
    cinema = CINEMAS_STORE.get(cinema_id)

    if not cinema or cinema["tenant_id"] != tenant_id:
        raise APIException(
            code="CINEMA_NOT_FOUND",
            message=f"Cinema '{cinema_id}' not found under current tenant.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    auditorium_id = f"aud-{uuid.uuid4().hex[:12]}"
    auditorium_record = {
        "id": auditorium_id,
        "tenant_id": tenant_id,
        "cinema_id": cinema_id,
        "name": payload.name,
        "capacity": payload.capacity,
        "auditorium_type": payload.auditorium_type,
        "status": "ACTIVE",
        "active_layout_version": 1,
    }
    AUDITORIUMS_STORE[auditorium_id] = auditorium_record

    # Automatically generate published layout v1 for newly created auditorium
    layout = _generate_default_layout(auditorium_id, tenant_id)
    LAYOUTS_STORE[layout["layout_id"]] = layout

    return StandardResponse(
        data=AuditoriumResponse(**auditorium_record),
        meta=ResponseMeta(request_id=request_id),
    )


@router.get("/cinemas/{cinema_id}/auditoriums", response_model=StandardResponse[List[AuditoriumResponse]])
async def list_cinema_auditoriums(
    cinema_id: str,
    request: Request,
    tenant_id: str = Depends(get_current_tenant_id),
):
    request_id = getattr(request.state, "request_id", None)
    cinema = CINEMAS_STORE.get(cinema_id)

    if not cinema or cinema["tenant_id"] != tenant_id:
        raise APIException(
            code="CINEMA_NOT_FOUND",
            message=f"Cinema '{cinema_id}' not found under current tenant.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    auditoriums = [
        AuditoriumResponse(**a)
        for a in AUDITORIUMS_STORE.values()
        if a["cinema_id"] == cinema_id and a["tenant_id"] == tenant_id
    ]

    return StandardResponse(
        data=auditoriums,
        meta=ResponseMeta(request_id=request_id, total=len(auditoriums)),
    )


@router.post("/auditoriums/{auditorium_id}/layouts", response_model=StandardResponse[AuditoriumLayoutResponse])
async def publish_auditorium_layout(
    auditorium_id: str,
    payload: LayoutPublishRequest,
    request: Request,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """
    Publishes a new immutable layout version for an auditorium.
    Enforces layout version incrementing and object identifier uniqueness.
    """
    request_id = getattr(request.state, "request_id", None)
    auditorium = AUDITORIUMS_STORE.get(auditorium_id)

    if not auditorium or auditorium["tenant_id"] != tenant_id:
        raise APIException(
            code="AUDITORIUM_NOT_FOUND",
            message=f"Auditorium '{auditorium_id}' not found under current tenant.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Invariant: Verify unique object identifiers and unique seat labels
    object_ids = set()
    seat_labels = set()
    seats_list = []

    for s in payload.seats:
        if s.object_identifier in object_ids:
            raise APIException(
                code="DUPLICATE_OBJECT_IDENTIFIER",
                message=f"Object identifier '{s.object_identifier}' is duplicated in layout.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        object_ids.add(s.object_identifier)

        label = f"{s.row_label}{s.seat_number}"
        if label in seat_labels:
            raise APIException(
                code="DUPLICATE_SEAT_LABEL",
                message=f"Seat label '{label}' is duplicated in layout.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        seat_labels.add(label)

        seats_list.append({
            "seat_id": f"seat-{auditorium_id}-{label.lower()}",
            "label": label,
            "row": s.row_label,
            "number": s.seat_number,
            "seat_type": s.seat_type,
            "position": [s.position_x, s.position_y, s.position_z],
            "eye_point": [s.position_x, round(s.position_y + 1.1, 3), s.position_z],
            "object_identifier": s.object_identifier,
        })

    # Increment layout version
    current_version = auditorium.get("active_layout_version", 1)
    new_version = current_version + 1
    auditorium["active_layout_version"] = new_version
    auditorium["capacity"] = len(seats_list)

    layout_id = f"lay-{auditorium_id}-v{new_version}"
    published_record = {
        "layout_id": layout_id,
        "auditorium_id": auditorium_id,
        "tenant_id": tenant_id,
        "version": new_version,
        "status": "PUBLISHED",
        "screen": payload.screen_configuration.model_dump(),
        "geometry_metadata": payload.geometry_metadata,
        "seats": seats_list,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    LAYOUTS_STORE[layout_id] = published_record

    return StandardResponse(
        data=AuditoriumLayoutResponse(
            layout_id=published_record["layout_id"],
            auditorium_id=published_record["auditorium_id"],
            version=published_record["version"],
            status=published_record["status"],
            screen=payload.screen_configuration,
            geometry_metadata=published_record["geometry_metadata"],
            seats=[LayoutSeatItem(**s) for s in seats_list],
            published_at=published_record["published_at"],
        ),
        meta=ResponseMeta(request_id=request_id),
    )
