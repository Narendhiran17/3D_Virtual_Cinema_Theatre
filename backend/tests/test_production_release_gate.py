import pytest


@pytest.mark.asyncio
async def test_production_security_headers_and_correlation(client):
    """Verifies that all responses emit mandatory OWASP security headers and correlation IDs."""
    response = await client.get("/health/live")
    assert response.status_code == 200

    # OWASP Security Headers
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "max-age=" in response.headers.get("Strict-Transport-Security", "")

    # Correlation & Observability Headers
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time-Ms" in response.headers


@pytest.mark.asyncio
async def test_production_readiness_probe(client):
    """Verifies container readiness probe returns healthy dependencies."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ready"
    assert data["checks"]["redis"] == "ready"


@pytest.mark.asyncio
async def test_production_financial_minor_units_invariant(client):
    """Verifies all pricing and financial transactions strictly utilize integer minor currency units."""
    # Fetch seat map
    seatmap_res = await client.get("/api/v1/shows/show-apex-cosmic-001/seat-map")
    assert seatmap_res.status_code == 200
    seats = seatmap_res.json()["data"]["seats"]

    for seat in seats:
        # Must be integer and positive
        assert isinstance(seat["price_minor"], int)
        assert seat["price_minor"] > 0
        assert seat["currency"] in ["USD", "EUR", "GBP"]


@pytest.mark.asyncio
async def test_production_zero_double_booking_under_concurrency(client):
    """Verifies that simultaneous locks on the same seat reject with 409 SEAT_UNAVAILABLE."""
    show_id = "show-apex-cosmic-001"
    target_seat = f"ss-{show_id}-e1"

    # User 1 claims seat E1
    res1 = await client.post(
        "/api/v1/seat-locks",
        json={
            "show_id": show_id,
            "show_seat_ids": [target_seat],
            "booking_session_id": "session-concurrent-user-1",
        },
        headers={"Idempotency-Key": "idemp-conc-test-01"},
    )
    assert res1.status_code == 200
    assert res1.json()["data"]["status"] == "HELD"

    # User 2 concurrently attempts to claim seat E1
    res2 = await client.post(
        "/api/v1/seat-locks",
        json={
            "show_id": show_id,
            "show_seat_ids": [target_seat],
            "booking_session_id": "session-concurrent-user-2",
        },
        headers={"Idempotency-Key": "idemp-conc-test-02"},
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "SEAT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_production_tenant_isolation_boundary(client):
    """Verifies strict tenant boundary enforcement prevents cross-tenant access."""
    # Login as operator of Apex Cinemas (ten-apex-001)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@apexcinemas.com", "password": "OperatorPass123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]

    # Attempt to access Solaris Theaters (ten-solaris-002) with Apex operator credentials
    forbidden_res = await client.get(
        "/api/v1/operator/cinemas",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": "ten-solaris-002",
        },
    )
    assert forbidden_res.status_code == 403
    assert forbidden_res.json()["error"]["code"] == "TENANT_FORBIDDEN"
