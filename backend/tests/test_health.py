import pytest


@pytest.mark.asyncio
async def test_liveness_endpoint(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "ok"
    assert "request_id" in data["meta"]
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_readiness_endpoint(client):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "ready"
    assert data["data"]["checks"]["database"] == "ready"
