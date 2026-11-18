import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from fastapi import APIRouter, Header, Request, status
from pydantic import BaseModel
from app.api.v1.endpoints.operator_shows import SHOWS_STORE, SHOW_SEATS_STORE
from app.core.errors import APIException
from app.core.websockets import ws_manager
from app.schemas.common import ResponseMeta, StandardResponse
from app.schemas.show import ShowSeatInventoryItem, ShowSeatMapResponse

router = APIRouter(tags=["Seat Inventory & 3D Mapping"])

# In-memory store for active seat locks
# Key: hold_id -> hold record
SEAT_LOCKS_STORE: Dict[str, dict] = {}


class SeatLockRequest(BaseModel):
    show_id: str
    show_seat_ids: List[str]
    booking_session_id: str


class SeatLockData(BaseModel):
    hold_id: str
    status: str
    expires_at: str
    show_seat_ids: List[str]


@router.get("/shows/{show_id}/seat-map", response_model=StandardResponse[ShowSeatMapResponse])
async def get_show_seat_map(show_id: str, request: Request):
    request_id = getattr(request.state, "request_id", None)
    show = SHOWS_STORE.get(show_id)

    if not show:
        raise APIException(
            code="SHOW_NOT_FOUND",
            message=f"Show '{show_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Check for expired holds and lazily release them
    now = datetime.now(timezone.utc)
    for hold in list(SEAT_LOCKS_STORE.values()):
        if hold["show_id"] == show_id and hold["status"] == "HELD":
            exp_dt = datetime.fromisoformat(hold["expires_at"])
            if now > exp_dt:
                hold["status"] = "EXPIRED"
                # Release seats
                seats = SHOW_SEATS_STORE.get(show_id, [])
                for s in seats:
                    if s["show_seat_id"] in hold["show_seat_ids"] and s["status"] == "HELD":
                        s["status"] = "AVAILABLE"

    seats = SHOW_SEATS_STORE.get(show_id, [])

    return StandardResponse(
        data=ShowSeatMapResponse(
            show_id=show_id,
            auditorium_id=show["auditorium_id"],
            layout_version=show["layout_version"],
            currency="USD",
            seats=[ShowSeatInventoryItem(**s) for s in seats],
        ),
        meta=ResponseMeta(request_id=request_id),
    )


@router.post("/seat-locks", response_model=StandardResponse[SeatLockData])
async def create_seat_lock(
    payload: SeatLockRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """
    Atomic seat lock creation with expiration timer and real-time WebSocket broadcast.
    Enforces that all requested seats must be AVAILABLE; otherwise rejects conflict with 409.
    """
    request_id = getattr(request.state, "request_id", None)
    show = SHOWS_STORE.get(payload.show_id)
    if not show:
        raise APIException(
            code="SHOW_NOT_FOUND",
            message=f"Show '{payload.show_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Check idempotency
    existing_hold = next((h for h in SEAT_LOCKS_STORE.values() if h.get("idempotency_key") == idempotencyKey(idempotency_key)), None)
    if existing_hold:
        return StandardResponse(
            data=SeatLockData(
                hold_id=existing_hold["hold_id"],
                status=existing_hold["status"],
                expires_at=existing_hold["expires_at"],
                show_seat_ids=existing_hold["show_seat_ids"],
            ),
            meta=ResponseMeta(request_id=request_id),
        )

    seats = SHOW_SEATS_STORE.get(payload.show_id, [])
    target_seats = [s for s in seats if s["show_seat_id"] in payload.show_seat_ids]

    if len(target_seats) != len(payload.show_seat_ids):
        raise APIException(
            code="SEAT_NOT_FOUND",
            message="One or more specified seats do not exist for this show.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Invariant: Concurrency verification
    unavailable_seats = [s["label"] for s in target_seats if s["status"] != "AVAILABLE"]
    if unavailable_seats:
        raise APIException(
            code="SEAT_UNAVAILABLE",
            message=f"Seats {unavailable_seats} are already held or confirmed by another customer.",
            status_code=status.HTTP_409_CONFLICT,
        )

    # Apply lock atomically
    hold_id = f"hold-{uuid.uuid4().hex[:12]}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    for s in target_seats:
        s["status"] = "HELD"

    hold_record = {
        "hold_id": hold_id,
        "tenant_id": show["tenant_id"],
        "show_id": payload.show_id,
        "show_seat_ids": payload.show_seat_ids,
        "booking_session_id": payload.booking_session_id,
        "status": "HELD",
        "expires_at": expires_at.isoformat(),
        "idempotency_key": idempotencyKey(idempotency_key),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    SEAT_LOCKS_STORE[hold_id] = hold_record

    # Broadcast real-time WebSocket event
    seat_labels = [s["label"] for s in target_seats]
    await ws_manager.broadcast_seat_event(payload.show_id, "seat.held", seat_labels, "HELD")

    return StandardResponse(
        data=SeatLockData(
            hold_id=hold_id,
            status="HELD",
            expires_at=expires_at.isoformat(),
            show_seat_ids=payload.show_seat_ids,
        ),
        meta=ResponseMeta(request_id=request_id),
    )


@router.delete("/seat-locks/{hold_id}", response_model=StandardResponse[dict])
async def release_seat_lock(hold_id: str, request: Request):
    """Releases held seats back to AVAILABLE."""
    request_id = getattr(request.state, "request_id", None)
    hold = SEAT_LOCKS_STORE.get(hold_id)

    if not hold or hold["status"] != "HELD":
        raise APIException(
            code="HOLD_NOT_FOUND",
            message=f"Active seat hold '{hold_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    hold["status"] = "RELEASED"
    show_id = hold["show_id"]
    seats = SHOW_SEATS_STORE.get(show_id, [])
    released_labels = []

    for s in seats:
        if s["show_seat_id"] in hold["show_seat_ids"]:
            s["status"] = "AVAILABLE"
            released_labels.append(s["label"])

    await ws_manager.broadcast_seat_event(show_id, "seat.released", released_labels, "AVAILABLE")

    return StandardResponse(
        data={"hold_id": hold_id, "status": "RELEASED", "released_seats": released_labels},
        meta=ResponseMeta(request_id=request_id),
    )


def idempotencyKey(key: str) -> str:
    return key.strip()
