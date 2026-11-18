import pytest


@pytest.mark.asyncio
async def test_create_and_list_operator_cinemas(client):
    # 1. Login as operator for ten-apex-001
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@apexcinemas.com", "password": "OperatorPass123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "ten-apex-001",
    }

    # 2. Create cinema branch
    payload = {
        "name": "Apex Grand Cinema - Brooklyn Commons",
        "address": {
            "street": "300 Ashland Pl",
            "city": "Brooklyn",
            "state": "NY",
            "postal_code": "11217",
            "country": "US",
        },
        "city": "Brooklyn",
        "country_code": "US",
        "timezone": "America/New_York",
    }
    create_res = await client.post("/api/v1/operator/cinemas", json=payload, headers=headers)
    assert create_res.status_code == 200
    cinema_id = create_res.json()["data"]["id"]
    assert create_res.json()["data"]["name"] == "Apex Grand Cinema - Brooklyn Commons"
    assert create_res.json()["data"]["tenant_id"] == "ten-apex-001"

    # 3. List operator cinemas
    list_res = await client.get("/api/v1/operator/cinemas", headers=headers)
    assert list_res.status_code == 200
    cinema_ids = [c["id"] for c in list_res.json()["data"]]
    assert cinema_id in cinema_ids


@pytest.mark.asyncio
async def test_create_auditorium_and_fetch_layout(client):
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

    # 2. Create Auditorium in cinema
    aud_payload = {
        "name": "Screen 2 - Dolby Atmos VIP",
        "capacity": 24,
        "auditorium_type": "DOLBY_ATMOS",
    }
    aud_res = await client.post(
        "/api/v1/operator/cinemas/cin-apex-001/auditoriums",
        json=aud_payload,
        headers=headers,
    )
    assert aud_res.status_code == 200
    auditorium_id = aud_res.json()["data"]["id"]
    assert aud_res.json()["data"]["auditorium_type"] == "DOLBY_ATMOS"

    # 3. Public Visualizer endpoint can fetch generated layout v1
    public_res = await client.get(f"/api/v1/auditoriums/{auditorium_id}/layout")
    assert public_res.status_code == 200
    layout_data = public_res.json()["data"]
    assert layout_data["auditorium_id"] == auditorium_id
    assert layout_data["version"] == 1
    assert len(layout_data["seats"]) > 0
    assert layout_data["screen"]["width"] == 16.0


@pytest.mark.asyncio
async def test_publish_custom_auditorium_layout_version(client):
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@apexcinemas.com", "password": "OperatorPass123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "ten-apex-001",
    }

    # Publish Layout Version 2 with custom 3D seating coordinates
    layout_payload = {
        "geometry_metadata": {
            "dimensions": {"width": 14.0, "length": 18.0, "slope_degrees": 7.0}
        },
        "screen_configuration": {
            "width": 12.0,
            "height": 5.5,
            "curve_radius": 20.0,
            "center": [0.0, 4.0, -12.0],
            "normal": [0.0, 0.0, 1.0],
        },
        "seats": [
            {
                "row_label": "A",
                "seat_number": "1",
                "seat_type": "STANDARD",
                "position_x": -1.5,
                "position_y": 0.8,
                "position_z": -3.0,
                "object_identifier": "SEAT_A_01",
            },
            {
                "row_label": "A",
                "seat_number": "2",
                "seat_type": "STANDARD",
                "position_x": 0.0,
                "position_y": 0.8,
                "position_z": -3.0,
                "object_identifier": "SEAT_A_02",
            },
            {
                "row_label": "A",
                "seat_number": "3",
                "seat_type": "PREMIUM",
                "position_x": 1.5,
                "position_y": 0.8,
                "position_z": -3.0,
                "object_identifier": "SEAT_A_03",
            },
        ],
    }

    pub_res = await client.post(
        "/api/v1/operator/auditoriums/aud-apex-imax-01/layouts",
        json=layout_payload,
        headers=headers,
    )
    assert pub_res.status_code == 200
    pub_data = pub_res.json()["data"]
    assert pub_data["version"] >= 2
    assert pub_data["status"] == "PUBLISHED"
    assert len(pub_data["seats"]) == 3


@pytest.mark.asyncio
async def test_publish_layout_rejects_duplicate_seat_labels(client):
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@apexcinemas.com", "password": "OperatorPass123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "ten-apex-001",
    }

    # Duplicate seat A1 in payload
    invalid_payload = {
        "screen_configuration": {
            "width": 12.0,
            "height": 5.5,
            "center": [0.0, 4.0, -12.0],
            "normal": [0.0, 0.0, 1.0],
        },
        "seats": [
            {
                "row_label": "A",
                "seat_number": "1",
                "seat_type": "STANDARD",
                "position_x": -1.0,
                "position_y": 0.8,
                "position_z": -3.0,
                "object_identifier": "SEAT_A_01",
            },
            {
                "row_label": "A",
                "seat_number": "1",
                "seat_type": "STANDARD",
                "position_x": 1.0,
                "position_y": 0.8,
                "position_z": -3.0,
                "object_identifier": "SEAT_A_02",
            },
        ],
    }
    res = await client.post(
        "/api/v1/operator/auditoriums/aud-apex-imax-01/layouts",
        json=invalid_payload,
        headers=headers,
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "DUPLICATE_SEAT_LABEL"
