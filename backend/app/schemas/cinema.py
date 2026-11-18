from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class CinemaAddress(BaseModel):
    street: str
    city: str
    state: Optional[str] = None
    postal_code: str
    country: str = "US"


class CinemaCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    address: CinemaAddress
    city: str
    country_code: str = Field(..., min_length=2, max_length=2)
    timezone: str = "America/New_York"


class CinemaUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[CinemaAddress] = None
    timezone: Optional[str] = None
    status: Optional[str] = None


class CinemaResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    address: Dict[str, Any]
    city: str
    country_code: str
    timezone: str
    status: str
    created_at: Optional[str] = None
