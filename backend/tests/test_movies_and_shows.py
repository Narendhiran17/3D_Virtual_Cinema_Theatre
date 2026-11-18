import pytest


@pytest.mark.asyncio
async def test_movie_creation_and_listing(client):
    # 1. Login as operator
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@apexcinemas.com", "password": "OperatorPass123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "ten-apex-001",
    }

    # 2. Create a movie
    movie_payload = {
        "title": "Quantum Horizon",
        "description": "A high-stakes quantum science fiction epic.",
        "duration_minutes": 142,
        "certification": "PG-13",
    }
    create_res = await client.post("/api/v1/operator/movies", json=movie_payload, headers=headers)
    assert create_res.status_code == 200
    movie_data = create_res.json()["data"]
    assert movie_data["title"] == "Quantum Horizon"
    assert movie_data["duration_minutes"] == 142

    # 3. List movies
    list_res = await client.get("/api/v1/operator/movies", headers=headers)
    assert list_res.status_code == 200
    titles = [m["title"] for m in list_res.json()["data"]]
    assert "Quantum Horizon" in titles


@pytest.mark.asyncio
async def test_schedule_show_and_generate_seat_inventory(client):
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@apexcinemas.com", "password": "OperatorPass123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "ten-apex-001",
    }

    # Schedule show on 2026-11-21 (separate day, no conflict)
    show_payload = {
        "cinema_id": "cin-apex-001",
        "auditorium_id": "aud-apex-imax-01",
        "movie_id": "mov-cosmic-odyssey",
        "starts_at": "2026-11-21T18:00:00Z",
        "ends_at": "2026-11-21T20:45:00Z",
        "timezone": "America/New_York",
        "format": "IMAX_3D",
        "pricing_overrides_minor": {
            "STANDARD": 2000,
            "PREMIUM": 2800,
        },
    }
    sched_res = await client.post("/api/v1/operator/shows", json=show_payload, headers=headers)
    assert sched_res.status_code == 200
    show_data = sched_res.json()["data"]
    show_id = show_data["id"]
    assert show_data["movie_title"] == "Cosmic Odyssey: 3D Experience"
    # Layout version 2 was published in previous test with 3 seats, so show gets 3 seats
    assert show_data["total_seats"] == 3

    # Verify public seat-map endpoint returns the generated seats with configured prices
    seatmap_res = await client.get(f"/api/v1/shows/{show_id}/seat-map")
    assert seatmap_res.status_code == 200
    seats = seatmap_res.json()["data"]["seats"]
    assert len(seats) == 3

    # Premium seat A3 should have 2800 minor units ($28.00)
    seat_a3 = next(s for s in seats if s["label"] == "A3")
    assert seat_a3["seat_type"] == "PREMIUM"
    assert seat_a3["price_minor"] == 2800

    # Standard seat A1 should have 2000 minor units ($20.00)
    seat_a1 = next(s for s in seats if s["label"] == "A1")
    assert seat_a1["seat_type"] == "STANDARD"
    assert seat_a1["price_minor"] == 2000


@pytest.mark.asyncio
async def test_schedule_show_conflict_detection_fails(client):
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@apexcinemas.com", "password": "OperatorPass123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "ten-apex-001",
    }

    # Attempt to schedule overlapping with existing show on 2026-11-20 (19:30 - 22:15)
    # New attempt: 20:00 - 23:00 (overlaps!)
    overlapping_payload = {
        "cinema_id": "cin-apex-001",
        "auditorium_id": "aud-apex-imax-01",
        "movie_id": "mov-cosmic-odyssey",
        "starts_at": "2026-11-20T20:00:00Z",
        "ends_at": "2026-11-20T23:00:00Z",
        "timezone": "America/New_York",
        "format": "IMAX_3D",
    }
    conflict_res = await client.post("/api/v1/operator/shows", json=overlapping_payload, headers=headers)
    assert conflict_res.status_code == 409
    error_json = conflict_res.json()["error"]
    assert error_json["code"] == "SHOW_SCHEDULE_CONFLICT"
    assert "conflicts with existing show" in error_json["message"]


@pytest.mark.asyncio
async def test_schedule_show_invalid_times_fails(client):
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@apexcinemas.com", "password": "OperatorPass123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "ten-apex-001",
    }

    # End time before start time
    invalid_time_payload = {
        "cinema_id": "cin-apex-001",
        "auditorium_id": "aud-apex-imax-01",
        "movie_id": "mov-cosmic-odyssey",
        "starts_at": "2026-11-22T20:00:00Z",
        "ends_at": "2026-11-22T19:00:00Z",
        "timezone": "America/New_York",
    }
    res = await client.post("/api/v1/operator/shows", json=invalid_time_payload, headers=headers)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_SHOW_TIMES"
