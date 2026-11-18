import uuid
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class SeatLock(Base, TimestampMixin):
    __tablename__ = "seat_locks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    show_id = Column(UUID(as_uuid=True), ForeignKey("shows.id", ondelete="CASCADE"), nullable=False, index=True)
    show_seat_id = Column(UUID(as_uuid=True), ForeignKey("show_seats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_session_id = Column(UUID(as_uuid=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="HELD")  # HELD, EXPIRED, RELEASED, CONSUMED


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_reference = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    show_id = Column(UUID(as_uuid=True), ForeignKey("shows.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, CONFIRMED, PAYMENT_FAILED, EXPIRED, CANCELLED
    total_minor = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    items = relationship("BookingItem", back_populates="booking", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="booking", cascade="all, delete-orphan")


class BookingItem(Base):
    __tablename__ = "booking_items"
    __table_args__ = (
        UniqueConstraint("booking_id", "show_seat_id", name="uq_booking_show_seat"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    show_seat_id = Column(UUID(as_uuid=True), ForeignKey("show_seats.id"), nullable=False)
    seat_label_snapshot = Column(String(20), nullable=False)
    seat_type_snapshot = Column(String(50), nullable=False)
    unit_price_minor = Column(BigInteger, nullable=False)

    # Relationships
    booking = relationship("Booking", back_populates="items")
