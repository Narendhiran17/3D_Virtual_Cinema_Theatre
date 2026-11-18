import pytest


@pytest.mark.asyncio
async def test_user_registration(client):
    payload = {
        "full_name": "Sarah Connor",
        "email": "sarah.connor@example.com",
        "password": "Password123!",
        "phone": "+1234567890",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["data"]["email"] == "sarah.connor@example.com"
    assert res_data["data"]["full_name"] == "Sarah Connor"
    assert "password" not in res_data["data"]
    assert "password_hash" not in res_data["data"]


@pytest.mark.asyncio
async def test_user_registration_duplicate_fails(client):
    payload = {
        "full_name": "Duplicate Sarah",
        "email": "sarah.connor@example.com",
        "password": "Password123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    error_data = response.json()
    assert error_data["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.asyncio
async def test_user_login_success(client):
    payload = {
        "email": "operator@apexcinemas.com",
        "password": "OperatorPass123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert "access_token" in res_data["data"]
    assert "refresh_token" in res_data["data"]
    assert res_data["data"]["token_type"] == "bearer"
    assert len(res_data["data"]["user"]["tenants"]) > 0


@pytest.mark.asyncio
async def test_user_login_invalid_password(client):
    payload = {
        "email": "operator@apexcinemas.com",
        "password": "WrongPassword!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_get_me_authenticated(client):
    # 1. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@apexcinemas.com", "password": "OperatorPass123!"},
    )
    token = login_res.json()["data"]["access_token"]

    # 2. Call /auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["data"]["email"] == "operator@apexcinemas.com"


@pytest.mark.asyncio
async def test_tenant_isolation_enforcement(client):
    # 1. Login as operator assigned to 'ten-apex-001'
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@apexcinemas.com", "password": "OperatorPass123!"},
    )
    token = login_res.json()["data"]["access_token"]

    # 2. Request with Authorized Tenant ID: SUCCESS (200)
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "ten-apex-001",
    }
    payload = {
        "name": "Apex Downtown Branch",
        "city": "Metropolis",
        "country_code": "US",
        "timezone": "America/New_York",
    }
    success_res = await client.post("/api/v1/cinemas", json=payload, headers=auth_headers)
    assert success_res.status_code == 200
    assert success_res.json()["data"]["tenant_id"] == "ten-apex-001"

    # 3. Attempt access to ANOTHER tenant's scope: FORBIDDEN (403)
    forbidden_headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "ten-unauthorized-cinema-888",
    }
    forbidden_res = await client.post("/api/v1/cinemas", json=payload, headers=forbidden_headers)
    assert forbidden_res.status_code == 403
    assert forbidden_res.json()["error"]["code"] == "TENANT_FORBIDDEN"


@pytest.mark.asyncio
async def test_platform_admin_cross_tenant_access(client):
    # Platform Admin can manage any tenant
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@platform.com", "password": "AdminPass123!"},
    )
    token = login_res.json()["data"]["access_token"]

    admin_headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "ten-any-cinema-999",
    }
    payload = {
        "name": "Global Partner Cinema",
        "city": "London",
        "country_code": "GB",
        "timezone": "Europe/London",
    }
    res = await client.post("/api/v1/cinemas", json=payload, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["data"]["tenant_id"] == "ten-any-cinema-999"
