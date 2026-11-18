import uuid
from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    password_hash = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="ACTIVE")  # ACTIVE, SUSPENDED, PENDING
    is_platform_admin = Column(Boolean, default=False, nullable=False)

    # Relationships
    tenant_memberships = relationship("TenantUser", back_populates="user", cascade="all, delete-orphan")
