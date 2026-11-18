import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from app.api.v1.endpoints.operator_cinemas import AUDITORIUMS_STORE, CINEMAS_STORE, LAYOUTS_STORE
from app.core.deps import get_current_tenant_id
from app.core.errors import APIException
from app.schemas.common import ResponseMeta, StandardResponse
from app.schemas.movie import MovieCreate, MovieResponse
from app.schemas.show import (
    ShowDetailResponse,
    ShowScheduleCreate,
    ShowSeatInventoryItem,
    ShowSeatMapResponse,
)

router = APIRouter(prefix="/operator", tags=["Operator Movie & Show Management"])

# In-memory stores for Sprint 4
MOVIES_STORE: Dict[str, dict] = {
    "mov-cosmic-odyssey": {
        "id": "mov-cosmic-odyssey",
        "tenant_id": "ten-apex-001",
        "title": "Cosmic Odyssey: 3D Experience",
        "description": "An interstellar journey beyond the boundaries of known space in photorealistic IMAX 3D.",
        "duration_minutes": 165,
        "certification": "PG-13",
        "poster_url": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23",
        "backdrop_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa",
        "status": "ACTIVE",
        "created_at": "2026-11-15T10:00:00Z",
    }
}

# Key: show_id -> show dict
SHOWS_STORE: Dict[str, dict] = {}

# Key: show_id -> list of show_seat dicts
SHOW_SEATS_STORE: Dict[str, List[dict]] = {}


def _parse_iso(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


# Seed an initial published show
_seed_show_id = "show-apex-cosmic-001"
SHOWS_STORE[_seed_show_id] = {
    "id": _seed_show_id,
    "tenant_id": "ten-apex-001",
    "cinema_id": "cin-apex-001",
    "auditorium_id": "aud-apex-imax-01",
    "movie_id": "mov-cosmic-odyssey",
    "movie_title": "Cosmic Odyssey: 3D Experience",
    "layout_version": 1,
    "starts_at": "2026-11-20T19:30:00+00:00",
    "ends_at": "2026-11-20T22:15:00+00:00",
    "timezone": "America/New_York",
    "format": "IMAX_3D",
    "status": "PUBLISHED",
    "total_seats": 50,
    "available_seats": 50,
    "created_at": "2026-11-15T12:00:00Z",
}

# Seed corresponding show_seats
_seed_layout = LAYOUTS_STORE.get("lay-aud-apex-imax-01-v1")
if _seed_layout:
    _seed_seats = []
    for s in _seed_layout["seats"]:
        price = 2500 if s["seat_type"] == "PREMIUM" else 1800
        _seed_seats.append({
            "show_seat_id": f"ss-{_seed_show_id}-{s['label'].lower()}",
            "seat_id": s["seat_id"],
            "label": s["label"],
            "row": s["row"],
            "number": s["number"],
            "seat_type": s["seat_type"],
            "price_minor": price,
            "currency": "USD",
            "status": "AVAILABLE",
            "version": 1,
            "position": s["position"],
            "eye_point": s["eye_point"],
            "object_identifier": s["object_identifier"],
        })
    SHOW_SEATS_STORE[_seed_show_id] = _seed_seats


# Movie Catalogue Endpoints
@router.post("/movies", response_model=StandardResponse[MovieResponse])
async def create_operator_movie(
    payload: MovieCreate,
    request: Request,
    tenant_id: str = Depends(get_current_tenant_id),
):
    request_id = getattr(request.state, "request_id", None)
    movie_id = f"mov-{uuid.uuid4().hex[:12]}"

    movie_record = {
        "id": movie_id,
        "tenant_id": tenant_id,
        "title": payload.title,
        "description": payload.description,
        "duration_minutes": payload.duration_minutes,
        "certification": payload.certification,
        "poster_url": payload.poster_url,
        "backdrop_url": payload.backdrop_url,
        "status": "ACTIVE",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    MOVIES_STORE[movie_id] = movie_record

    return StandardResponse(
        data=MovieResponse(**movie_record),
        meta=ResponseMeta(request_id=request_id),
    )


@router.get("/movies", response_model=StandardResponse[List[MovieResponse]])
async def list_operator_movies(
    request: Request,
    tenant_id: str = Depends(get_current_tenant_id),
):
    request_id = getattr(request.state, "request_id", None)
    movies = [MovieResponse(**m) for m in MOVIES_STORE.values() if m["tenant_id"] == tenant_id]

    return StandardResponse(
        data=movies,
        meta=ResponseMeta(request_id=request_id, total=len(movies)),
    )


# Show Scheduling Endpoints
@router.post("/shows", response_model=StandardResponse[ShowDetailResponse])
async def schedule_show(
    payload: ShowScheduleCreate,
    request: Request,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """
    Schedules a new show with conflict detection and automated show-seat availability generation.
    Enforces that no two active shows can overlap in the same auditorium.
    """
    request_id = getattr(request.state, "request_id", None)

    # 1. Verify Cinema & Auditorium belong to this tenant
    cinema = CINEMAS_STORE.get(payload.cinema_id)
    if not cinema or cinema["tenant_id"] != tenant_id:
        raise APIException(
            code="CINEMA_NOT_FOUND",
            message=f"Cinema '{payload.cinema_id}' not found under current tenant.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    auditorium = AUDITORIUMS_STORE.get(payload.auditorium_id)
    if not auditorium or auditorium["tenant_id"] != tenant_id:
        raise APIException(
            code="AUDITORIUM_NOT_FOUND",
            message=f"Auditorium '{payload.auditorium_id}' not found under current tenant.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. Verify Movie exists
    movie = MOVIES_STORE.get(payload.movie_id)
    if not movie or movie["tenant_id"] != tenant_id:
        raise APIException(
            code="MOVIE_NOT_FOUND",
            message=f"Movie '{payload.movie_id}' not found in tenant catalogue.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 3. Time Validation
    start_dt = _parse_iso(payload.starts_at)
    end_dt = _parse_iso(payload.ends_at)
    if end_dt <= start_dt:
        raise APIException(
            code="INVALID_SHOW_TIMES",
            message="Show end time must be after start time.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 4. Invariant: Auditorium Conflict Detection
    # Overlap occurs if existing_start < new_end and existing_end > new_start
    for existing_show in SHOWS_STORE.values():
        if (
            existing_show["auditorium_id"] == payload.auditorium_id
            and existing_show["status"] != "CANCELLED"
        ):
            ex_start = _parse_iso(existing_show["starts_at"])
            ex_end = _parse_iso(existing_show["ends_at"])
            if ex_start < end_dt and ex_end > start_dt:
                raise APIException(
                    code="SHOW_SCHEDULE_CONFLICT",
                    message=(
                        f"Show time conflicts with existing show '{existing_show['movie_title']}' "
                        f"({existing_show['starts_at']} - {existing_show['ends_at']}) in this auditorium."
                    ),
                    status_code=status.HTTP_409_CONFLICT,
                )

    # 5. Resolve active layout version
    layout_ver = auditorium.get("active_layout_version", 1)
    layout_id = f"lay-{payload.auditorium_id}-v{layout_ver}"
    layout = LAYOUTS_STORE.get(layout_id)
    if not layout:
        # Fallback layout if newly created
        from app.api.v1.endpoints.operator_cinemas import _generate_default_layout
        layout = _generate_default_layout(payload.auditorium_id, tenant_id)
        LAYOUTS_STORE[layout_id] = layout

    # 6. Initialize Show Seats with Pricing Rules
    show_id = f"show-{uuid.uuid4().hex[:12]}"
    pricing_map = payload.pricing_overrides_minor or {
        "STANDARD": 1800,
        "PREMIUM": 2500,
        "RECLINER": 3200,
        "ACCESSIBLE": 1800,
    }

    generated_seats: List[dict] = []
    for seat in layout["seats"]:
        seat_type = seat.get("seat_type", "STANDARD")
        unit_price = pricing_map.get(seat_type, 1800)

        generated_seats.append({
            "show_seat_id": f"ss-{show_id}-{seat['label'].lower()}",
            "seat_id": seat["seat_id"],
            "label": seat["label"],
            "row": seat["row"],
            "number": seat["number"],
            "seat_type": seat_type,
            "price_minor": unit_price,
            "currency": "USD",
            "status": "AVAILABLE",
            "version": 1,
            "position": seat["position"],
            "eye_point": seat["eye_point"],
            "object_identifier": seat["object_identifier"],
        })

    SHOW_SEATS_STORE[show_id] = generated_seats

    show_record = {
        "id": show_id,
        "tenant_id": tenant_id,
        "cinema_id": payload.cinema_id,
        "auditorium_id": payload.auditorium_id,
        "movie_id": payload.movie_id,
        "movie_title": movie["title"],
        "layout_version": layout_ver,
        "starts_at": payload.starts_at,
        "ends_at": payload.ends_at,
        "timezone": payload.timezone,
        "format": payload.format,
        "status": "PUBLISHED",
        "total_seats": len(generated_seats),
        "available_seats": len(generated_seats),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    SHOWS_STORE[show_id] = show_record

    return StandardResponse(
        data=ShowDetailResponse(**show_record),
        meta=ResponseMeta(request_id=request_id),
    )


@router.get("/shows", response_model=StandardResponse[List[ShowDetailResponse]])
async def list_operator_shows(
    request: Request,
    cinema_id: Optional[str] = None,
    auditorium_id: Optional[str] = None,
    tenant_id: str = Depends(get_current_tenant_id),
):
    request_id = getattr(request.state, "request_id", None)
    shows = [
        ShowDetailResponse(**s)
        for s in SHOWS_STORE.values()
        if s["tenant_id"] == tenant_id
        and (not cinema_id or s["cinema_id"] == cinema_id)
        and (not auditorium_id or s["auditorium_id"] == auditorium_id)
    ]

    return StandardResponse(
        data=shows,
        meta=ResponseMeta(request_id=request_id, total=len(shows)),
    )
