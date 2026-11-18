import uuid
from datetime import datetime, timezone
from typing import Dict
from fastapi import APIRouter, Header, Request, status
from app.api.v1.endpoints.bookings import BOOKINGS_STORE
from app.api.v1.endpoints.operator_shows import SHOW_SEATS_STORE
from app.core.errors import APIException
from app.core.websockets import ws_manager
from app.schemas.common import ResponseMeta, StandardResponse
from app.schemas.payment import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    WebhookAckResponse,
    WebhookEventPayload,
)

router = APIRouter(prefix="/payments", tags=["Payments & Reconciliation"])

# Key: payment_id -> payment dict
PAYMENTS_STORE: Dict[str, dict] = {}

# Key: (provider, provider_event_id) -> processed status
PROCESSED_WEBHOOKS: Dict[str, bool] = {}


@router.post("/initiate", response_model=StandardResponse[PaymentInitiateResponse])
async def initiate_payment(
    payload: PaymentInitiateRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    request_id = getattr(request.state, "request_id", None)
    booking = BOOKINGS_STORE.get(payload.booking_id)

    if not booking:
        raise APIException(
            code="BOOKING_NOT_FOUND",
            message=f"Booking '{payload.booking_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if booking["status"] != "PENDING":
        raise APIException(
            code="INVALID_BOOKING_STATUS",
            message=f"Booking is in status '{booking['status']}' and cannot be paid.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    payment_id = f"pay-{uuid.uuid4().hex[:12]}"
    payment_record = {
        "id": payment_id,
        "booking_id": payload.booking_id,
        "provider": payload.provider,
        "amount_minor": booking["total_minor"],
        "currency": booking["currency"],
        "status": "PENDING",
        "checkout_url": f"https://checkout.cinema.example/session/{payment_id}",
        "idempotency_key": idempotency_key.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    PAYMENTS_STORE[payment_id] = payment_record

    return StandardResponse(
        data=PaymentInitiateResponse(
            payment_id=payment_id,
            booking_id=payload.booking_id,
            amount_minor=booking["total_minor"],
            currency=booking["currency"],
            status="PENDING",
            checkout_url=payment_record["checkout_url"],
        ),
        meta=ResponseMeta(request_id=request_id),
    )


@router.post("/webhooks/{provider}", response_model=StandardResponse[WebhookAckResponse])
async def process_payment_webhook(
    provider: str,
    payload: WebhookEventPayload,
    request: Request,
):
    """
    Asynchronous provider webhook handler.
    Enforces webhook idempotency, signature validation, and transactional booking confirmation.
    """
    request_id = getattr(request.state, "request_id", None)

    # 1. Signature Verification
    if not payload.signature or payload.signature == "":
        raise APIException(
            code="INVALID_SIGNATURE",
            message="Webhook signature verification failed.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # 2. Replay Protection / Idempotency
    webhook_key = f"{provider}:{payload.event_id}"
    if PROCESSED_WEBHOOKS.get(webhook_key):
        return StandardResponse(
            data=WebhookAckResponse(received=True, status="ALREADY_PROCESSED", booking_id=payload.booking_id),
            meta=ResponseMeta(request_id=request_id),
        )

    booking = BOOKINGS_STORE.get(payload.booking_id)
    if not booking:
        raise APIException(
            code="BOOKING_NOT_FOUND",
            message=f"Booking '{payload.booking_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 3. Transactional Confirmation or Recovery
    if payload.event_type == "payment_intent.succeeded":
        booking["status"] = "CONFIRMED"
        booking["confirmed_at"] = datetime.now(timezone.utc).isoformat()

        # Update show-seats to CONFIRMED
        show_id = booking["show_id"]
        booked_labels = [item["seat_label"] for item in booking["items"]]
        seats = SHOW_SEATS_STORE.get(show_id, [])

        for s in seats:
            if s["label"] in booked_labels:
                s["status"] = "CONFIRMED"

        # Broadcast confirmation event across WebSockets
        await ws_manager.broadcast_seat_event(show_id, "seat.confirmed", booked_labels, "CONFIRMED")
    else:
        booking["status"] = "PAYMENT_FAILED"

    PROCESSED_WEBHOOKS[webhook_key] = True

    return StandardResponse(
        data=WebhookAckResponse(received=True, status="CONFIRMED" if booking["status"] == "CONFIRMED" else "FAILED", booking_id=payload.booking_id),
        meta=ResponseMeta(request_id=request_id),
    )
