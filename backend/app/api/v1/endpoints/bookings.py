import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Header, Request, status
from app.api.v1.endpoints.operator_cinemas import AUDITORIUMS_STORE, CINEMAS_STORE
from app.api.v1.endpoints.operator_shows import MOVIES_STORE, SHOWS_STORE, SHOW_SEATS_STORE
from app.api.v1.endpoints.seats import SEAT_LOCKS_STORE
from app.core.deps import AuthenticatedUser, get_current_user, get_optional_current_user
from app.core.errors import APIException
from app.core.websockets import ws_manager
from app.schemas.booking import (
    BookingDetailResponse,
    BookingItemResponse,
    CreateBookingRequest,
)
from app.schemas.common import ResponseMeta, StandardResponse

router = APIRouter(prefix="/bookings", tags=["Bookings & Checkout"])

# Key: booking_id -> booking record
BOOKINGS_STORE: Dict[str, dict] = {}


@router.post("", response_model=StandardResponse[BookingDetailResponse])
async def create_booking(
    payload: CreateBookingRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
):
    """
    Creates a PENDING booking from a valid, active seat hold.
    Authoritatively computes total from show-seat price snapshots (never client input).
    """
    request_id = getattr(request.state, "request_id", None)
    hold = SEAT_LOCKS_STORE.get(payload.hold_id)

    if not hold or hold["status"] != "HELD":
        raise APIException(
            code="HOLD_INVALID_OR_EXPIRED",
            message="Seat hold has expired or is invalid. Please select your seats again.",
            status_code=status.HTTP_410_GONE,
        )

    # Check if hold expired by time
    if datetime.now(timezone.utc) > datetime.fromisoformat(hold["expires_at"]):
        hold["status"] = "EXPIRED"
        raise APIException(
            code="HOLD_EXPIRED",
            message="Seat hold timer has elapsed. Seats have been returned to inventory.",
            status_code=status.HTTP_410_GONE,
        )

    show = SHOWS_STORE.get(hold["show_id"])
    cinema = CINEMAS_STORE.get(show["cinema_id"]) if show else None
    auditorium = AUDITORIUMS_STORE.get(show["auditorium_id"]) if show else None
    movie = MOVIES_STORE.get(show["movie_id"]) if show else None

    # Resolve held show-seats to create immutable booking items
    show_seats = SHOW_SEATS_STORE.get(hold["show_id"], [])
    held_seats = [s for s in show_seats if s["show_seat_id"] in hold["show_seat_ids"]]

    items: List[dict] = []
    total_minor = 0

    for s in held_seats:
        unit_price = s["price_minor"]
        total_minor += unit_price
        items.append({
            "seat_label": s["label"],
            "seat_type": s["seat_type"],
            "unit_price_minor": unit_price,
        })

    booking_id = f"bk-{uuid.uuid4().hex[:12]}"
    booking_ref = f"CIN-2026-{uuid.uuid4().hex[:4].upper()}"
    user_id = current_user.id if current_user else "usr-guest-customer"

    booking_record = {
        "id": booking_id,
        "booking_reference": booking_ref,
        "tenant_id": show["tenant_id"],
        "user_id": user_id,
        "customer_email": payload.customer_contact.email,
        "show_id": show["id"],
        "movie_title": movie["title"] if movie else "Cinema Screening",
        "cinema_name": cinema["name"] if cinema else "Cinema Branch",
        "auditorium_name": auditorium["name"] if auditorium else "Auditorium",
        "starts_at": show["starts_at"],
        "status": "PENDING",
        "total_minor": total_minor,
        "currency": "USD",
        "items": items,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "confirmed_at": None,
    }
    BOOKINGS_STORE[booking_id] = booking_record

    # Transition hold to CONSUMED
    hold["status"] = "CONSUMED"

    return StandardResponse(
        data=BookingDetailResponse(**booking_record),
        meta=ResponseMeta(request_id=request_id),
    )


@router.get("/me", response_model=StandardResponse[List[BookingDetailResponse]])
async def get_my_bookings(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Returns booking history for the authenticated customer."""
    request_id = getattr(request.state, "request_id", None)
    my_bookings = [
        BookingDetailResponse(**b)
        for b in BOOKINGS_STORE.values()
        if b.get("user_id") == current_user.id or b.get("customer_email") == current_user.email
    ]

    return StandardResponse(
        data=my_bookings,
        meta=ResponseMeta(request_id=request_id, total=len(my_bookings)),
    )


@router.get("/{booking_id}", response_model=StandardResponse[BookingDetailResponse])
async def get_booking_details(booking_id: str, request: Request):
    request_id = getattr(request.state, "request_id", None)
    booking = BOOKINGS_STORE.get(booking_id)

    if not booking:
        raise APIException(
            code="BOOKING_NOT_FOUND",
            message=f"Booking '{booking_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return StandardResponse(
        data=BookingDetailResponse(**booking),
        meta=ResponseMeta(request_id=request_id),
    )


@router.post("/{booking_id}/cancel", response_model=StandardResponse[dict])
async def cancel_booking(
    booking_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Executes booking cancellation and seat release according to platform policy.
    Releases all reserved show-seats back to AVAILABLE and notifies real-time subscribers.
    """
    request_id = getattr(request.state, "request_id", None)
    booking = BOOKINGS_STORE.get(booking_id)

    if not booking:
        raise APIException(
            code="BOOKING_NOT_FOUND",
            message=f"Booking '{booking_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Permission check: customer must own booking unless platform admin
    if not current_user.is_platform_admin and booking.get("user_id") != current_user.id:
        raise APIException(
            code="FORBIDDEN",
            message="You do not have permission to cancel this booking.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if booking["status"] == "CANCELLED":
        raise APIException(
            code="ALREADY_CANCELLED",
            message="This booking is already cancelled.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Transition booking status
    booking["status"] = "CANCELLED"

    # Release seats back to AVAILABLE
    show_id = booking["show_id"]
    released_labels = [item["seat_label"] for item in booking["items"]]
    seats = SHOW_SEATS_STORE.get(show_id, [])

    for s in seats:
        if s["label"] in released_labels:
            s["status"] = "AVAILABLE"

    # Broadcast seat release event over WebSockets
    await ws_manager.broadcast_seat_event(show_id, "seat.released", released_labels, "AVAILABLE")

    return StandardResponse(
        data={
            "booking_id": booking_id,
            "status": "CANCELLED",
            "released_seats": released_labels,
            "refund_status": "REFUNDED_TO_ORIGINAL_PAYMENT",
        },
        meta=ResponseMeta(request_id=request_id),
    )
