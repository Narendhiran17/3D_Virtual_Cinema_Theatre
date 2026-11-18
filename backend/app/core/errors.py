from typing import Any, List, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse


class APIException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[List[Any]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)


class SeatUnavailableException(APIException):
    def __init__(self, message: str = "One or more selected seats are no longer available."):
        super().__init__(
            code="SEAT_UNAVAILABLE",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class SeatLockExpiredException(APIException):
    def __init__(self, message: str = "Seat lock has expired."):
        super().__init__(
            code="SEAT_LOCK_EXPIRED",
            message=message,
            status_code=status.HTTP_410_GONE,
        )


class TenantAccessDeniedException(APIException):
    def __init__(self, message: str = "Access to tenant resource is forbidden."):
        super().__init__(
            code="TENANT_FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact support.",
                "details": [],
                "request_id": request_id,
            }
        },
    )
