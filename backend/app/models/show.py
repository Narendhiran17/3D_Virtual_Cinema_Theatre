import uuid
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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


class Show(Base, TimestampMixin):
    __tablename__ = "shows"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="check_show_time_valid"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    cinema_id = Column(UUID(as_uuid=True), ForeignKey("cinemas.id", ondelete="CASCADE"), nullable=False, index=True)
    auditorium_id = Column(UUID(as_uuid=True), ForeignKey("auditoriums.id", ondelete="CASCADE"), nullable=False, index=True)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    layout_version_id = Column(UUID(as_uuid=True), ForeignKey("auditorium_layout_versions.id"), nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ends_at = Column(DateTime(timezone=True), nullable=False, index=True)
    timezone = Column(String(100), nullable=False, default="UTC")
    format = Column(String(50), nullable=False, default="IMAX_3D")
    status = Column(String(50), nullable=False, default="PUBLISHED")  # DRAFT, PUBLISHED, CANCELLED

    # Relationships
    movie = relationship("Movie", back_populates="shows")
    show_seats = relationship("ShowSeat", back_populates="show", cascade="all, delete-orphan")


class ShowSeat(Base, TimestampMixin):
    __tablename__ = "show_seats"
    __table_args__ = (
        UniqueConstraint("show_id", "seat_id", name="uq_show_seat"),
        UniqueConstraint("tenant_id", "id", name="uq_tenant_show_seat"),
        CheckConstraint("price_minor >= 0", name="check_show_seat_price_positive"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    show_id = Column(UUID(as_uuid=True), ForeignKey("shows.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_id = Column(UUID(as_uuid=True), ForeignKey("seats.id", ondelete="CASCADE"), nullable=False, index=True)
    price_minor = Column(BigInteger, nullable=False)  # in cents / minor currency units (e.g. 2500 = $25.00)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(String(50), nullable=False, default="AVAILABLE")  # AVAILABLE, HELD, CONFIRMED, BLOCKED
    version = Column(BigInteger, nullable=False, default=1)  # Optimistic lock version

    # Relationships
    show = relationship("Show", back_populates="show_seats")
    seat = relationship("Seat")
