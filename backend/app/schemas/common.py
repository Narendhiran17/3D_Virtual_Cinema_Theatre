from typing import Generic, Optional, TypeVar, Any, Dict
from pydantic import BaseModel

T = TypeVar("T")


class ResponseMeta(BaseModel):
    request_id: Optional[str] = None
    page: Optional[int] = None
    page_size: Optional[int] = None
    total: Optional[int] = None


class StandardResponse(BaseModel, Generic[T]):
    data: T
    meta: Optional[ResponseMeta] = None


class HealthStatus(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    checks: Optional[Dict[str, str]] = None
