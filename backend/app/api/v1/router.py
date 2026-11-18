from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    health,
    cinemas,
    shows,
    seats,
    bookings,
    payments,
    operator_cinemas,
    operator_shows,
    auditoriums,
    websockets,
    platform_admin,
)

api_router = APIRouter()

# Core discovery & auth
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(cinemas.router)
api_router.include_router(shows.router)
api_router.include_router(seats.router)
api_router.include_router(bookings.router)
api_router.include_router(payments.router)

# Real-time WebSocket
api_router.include_router(websockets.router)

# Operator & 3D Layout routes (Sprint 3 & 4)
api_router.include_router(operator_cinemas.router)
api_router.include_router(operator_shows.router)
api_router.include_router(auditoriums.router)

# Central Platform Admin routes (Sprint 10 & 11)
api_router.include_router(platform_admin.router)

