from typing import List, Optional
from pydantic import BaseModel, EmailStr


class CustomerContact(BaseModel):
    email: EmailStr
    phone: Optional[str] = None


class BookingItemResponse(BaseModel):
    seat_label: str
    seat_type: str
    unit_price_minor: int


class CreateBookingRequest(BaseModel):
    hold_id: str
    customer_contact: CustomerContact


class BookingDetailResponse(BaseModel):
    id: str
    booking_reference: str
    tenant_id: str
    show_id: str
    movie_title: str
    cinema_name: str
    auditorium_name: str
    starts_at: str
    status: str
    total_minor: int
    currency: str
    items: List[BookingItemResponse]
    created_at: str
    confirmed_at: Optional[str] = None
