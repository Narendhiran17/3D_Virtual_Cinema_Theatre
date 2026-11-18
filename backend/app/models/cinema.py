import uuid
from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Cinema(Base, TimestampMixin):
    __tablename__ = "cinemas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_tenant_cinema"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    address = Column(JSONB, nullable=False)  # {"street": "...", "city": "...", "state": "...", "postal_code": "..."}
    city = Column(String(100), nullable=False, index=True)
    country_code = Column(String(2), nullable=False)
    timezone = Column(String(100), nullable=False, default="UTC")
    status = Column(String(50), nullable=False, default="ACTIVE")

    # Relationships
    auditoriums = relationship("Auditorium", back_populates="cinema", cascade="all, delete-orphan")
