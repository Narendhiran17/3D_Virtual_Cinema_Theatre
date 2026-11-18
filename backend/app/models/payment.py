import uuid
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # stripe, mock, adyen
    provider_transaction_id = Column(String(100), nullable=True, index=True)
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(String(50), nullable=False, default="CREATED")  # CREATED, PENDING, SUCCEEDED, FAILED, REFUNDED

    # Relationships
    booking = relationship("Booking", back_populates="payments")
    attempts = relationship("PaymentAttempt", back_populates="payment", cascade="all, delete-orphan")


class PaymentAttempt(Base, TimestampMixin):
    __tablename__ = "payment_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    provider_reference = Column(String(100), nullable=True)
    attempt_status = Column(String(50), nullable=False, default="INITIATED")

    # Relationships
    payment = relationship("Payment", back_populates="attempts")


class PaymentWebhookEvent(Base, TimestampMixin):
    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_provider_event"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), nullable=False)
    provider_event_id = Column(String(100), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(Text, nullable=False)
    processing_status = Column(String(50), nullable=False, default="PENDING")  # PENDING, PROCESSED, FAILED
    received_at = Column(DateTime(timezone=True), nullable=False)
