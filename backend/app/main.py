from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.core.middleware import (
    RateLimiterMiddleware,
    RequestCorrelationMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.errors import (
    APIException,
    api_exception_handler,
    generic_exception_handler,
)
from app.api.v1.router import api_router
from app.api.v1.endpoints.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} starting in [{settings.APP_ENV}] mode.")
    yield
    logger.info(f"{settings.APP_NAME} shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-tenant cinema management and ticket-booking platform with photorealistic 3D seat selection",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
is_wildcard = "*" in settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if not is_wildcard else ["*"],
    allow_origin_regex=r"^https:\/\/.*\.vercel\.app$" if not is_wildcard else None,
    allow_credentials=not is_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Production Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Rate Limiter Middleware
app.add_middleware(RateLimiterMiddleware, requests_per_minute=120)

# Request ID Correlation and Logging Middleware
app.add_middleware(RequestCorrelationMiddleware)

# Error handlers
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Top-level direct health check routes for orchestrators (e.g., K8s, Docker)
app.include_router(health_router)

# Versioned API routes
app.include_router(api_router, prefix="/api/v1")

