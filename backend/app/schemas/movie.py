from typing import Optional
from pydantic import BaseModel, Field


class MovieCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    duration_minutes: int = Field(..., gt=0)
    certification: Optional[str] = "PG-13"
    release_date: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None


class MovieResponse(BaseModel):
    id: str
    tenant_id: str
    title: str
    description: Optional[str] = None
    duration_minutes: int
    certification: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    status: str
    created_at: Optional[str] = None
