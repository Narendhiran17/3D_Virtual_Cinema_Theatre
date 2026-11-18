import time
import uuid
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from app.core.logging import logger


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start_time = time.time()
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"

        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"status={response.status_code} duration={process_time:.2f}ms"
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Applies OWASP recommended production security headers to all HTTP responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Sliding window in-memory rate limiter protecting sensitive API routes.
    Limits clients to 60 requests/minute on sensitive routes (auth, booking, payment initiation).
    """

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.clients = defaultdict(list)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Rate limit only state-mutating and sensitive endpoints
        sensitive_paths = ["/api/v1/auth/login", "/api/v1/seat-locks", "/api/v1/payments/initiate"]
        if request.url.path in sensitive_paths:
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            cutoff = now - 60.0

            # Prune timestamps older than 60 seconds
            self.clients[client_ip] = [t for t in self.clients[client_ip] if t > cutoff]

            if len(self.clients[client_ip]) >= self.requests_per_minute:
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please slow down and try again later.",
                        },
                        "meta": {"request_id": getattr(request.state, "request_id", None)},
                    },
                )

            self.clients[client_ip].append(now)

        return await call_next(request)

