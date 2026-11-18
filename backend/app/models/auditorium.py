import uuid
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Auditorium(Base, TimestampMixin):
    __tablename__ = "auditoriums"
    __table_args__ = (
        UniqueConstraint("tenant_id", "cinema_id", "name", name="uq_tenant_cinema_auditorium_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    cinema_id = Column(UUID(as_uuid=True), ForeignKey("cinemas.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    capacity = Column(Integer, nullable=False, default=0)
    auditorium_type = Column(String(50), nullable=False, default="STANDARD")  # IMAX_3D, DOLBY_ATMOS, STANDARD
    status = Column(String(50), nullable=False, default="ACTIVE")

    # Relationships
    cinema = relationship("Cinema", back_populates="auditoriums")
    layouts = relationship("AuditoriumLayoutVersion", back_populates="auditorium", cascade="all, delete-orphan")
    seats = relationship("Seat", back_populates="auditorium", cascade="all, delete-orphan")


class AuditoriumLayoutVersion(Base, TimestampMixin):
    __tablename__ = "auditorium_layout_versions"
    __table_args__ = (
        UniqueConstraint("auditorium_id", "version", name="uq_auditorium_layout_version"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    auditorium_id = Column(UUID(as_uuid=True), ForeignKey("auditoriums.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    geometry_metadata = Column(JSONB, nullable=False)  # {"dimensions": {"width": 18.0, "length": 22.0, "slope": 8.5}}
    screen_configuration = Column(JSONB, nullable=False)  # {"width": 16.0, "height": 7.0, "curve_radius": 24.0, "center": [0, 4.5, -14]}
    status = Column(String(50), nullable=False, default="DRAFT")  # DRAFT, PUBLISHED, ARCHIVED
    published_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    auditorium = relationship("Auditorium", back_populates="layouts")
    mappings = relationship("Seat3DMapping", back_populates="layout_version", cascade="all, delete-orphan")


class Seat(Base, TimestampMixin):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("auditorium_id", "row_label", "seat_number", name="uq_auditorium_row_seat"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    auditorium_id = Column(UUID(as_uuid=True), ForeignKey("auditoriums.id", ondelete="CASCADE"), nullable=False, index=True)
    row_label = Column(String(10), nullable=False)
    seat_number = Column(String(10), nullable=False)
    seat_type = Column(String(50), nullable=False, default="STANDARD")  # STANDARD, PREMIUM, RECLINER, ACCESSIBLE
    position_x = Column(Numeric(8, 3), nullable=False)
    position_y = Column(Numeric(8, 3), nullable=False)
    position_z = Column(Numeric(8, 3), nullable=False)
    rotation = Column(JSONB, nullable=True)
    accessibility_metadata = Column(JSONB, nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE")

    # Relationships
    auditorium = relationship("Auditorium", back_populates="seats")
    mappings = relationship("Seat3DMapping", back_populates="seat", cascade="all, delete-orphan")


class Seat3DMapping(Base):
    __tablename__ = "seat_3d_mappings"
    __table_args__ = (
        UniqueConstraint("layout_version_id", "seat_id", name="uq_layout_version_seat"),
        UniqueConstraint("layout_version_id", "object_identifier", name="uq_layout_version_object_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    layout_version_id = Column(UUID(as_uuid=True), ForeignKey("auditorium_layout_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_id = Column(UUID(as_uuid=True), ForeignKey("seats.id", ondelete="CASCADE"), nullable=False, index=True)
    object_identifier = Column(String(100), nullable=False)  # e.g., "SEAT_A_05"
    local_transform = Column(JSONB, nullable=False)

    # Relationships
    layout_version = relationship("AuditoriumLayoutVersion", back_populates="mappings")
    seat = relationship("Seat", back_populates="mappings")
