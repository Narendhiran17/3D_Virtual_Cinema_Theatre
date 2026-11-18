from typing import Optional
from pydantic import BaseModel


class PaymentInitiateRequest(BaseModel):
    booking_id: str
    provider: str = "mock"
    return_url: str = "http://localhost:5173/booking/result"


class PaymentInitiateResponse(BaseModel):
    payment_id: str
    booking_id: str
    amount_minor: int
    currency: str
    status: str
    checkout_url: str


class WebhookEventPayload(BaseModel):
    event_id: str
    event_type: str  # payment_intent.succeeded, payment_intent.failed
    provider: str
    payment_id: str
    booking_id: str
    amount_minor: int
    signature: str


class WebhookAckResponse(BaseModel):
    received: bool
    status: str
    booking_id: str
