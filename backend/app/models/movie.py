import uuid
from sqlalchemy import Column, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Movie(Base, TimestampMixin):
    __tablename__ = "movies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "title", name="uq_tenant_movie_title"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    release_date = Column(Date, nullable=True)
    certification = Column(String(20), nullable=True)  # PG, PG-13, R, NC-17
    poster_url = Column(String(500), nullable=True)
    backdrop_url = Column(String(500), nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE")

    # Relationships
    shows = relationship("Show", back_populates="movie", cascade="all, delete-orphan")
