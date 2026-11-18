import pytest


@pytest.mark.asyncio
async def test_platform_admin_unauthorized_access_rejected(client):
    # Unauthenticated request
    res = await client.get("/api/v1/platform/tenants")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"

    # Operator (non-platform-admin) request
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@apexcinemas.com", "password": "OperatorPass123!"},
    )
    assert login_res.status_code == 200
    op_token = login_res.json()["data"]["access_token"]

    forbidden_res = await client.get(
        "/api/v1/platform/tenants",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert forbidden_res.status_code == 403
    assert forbidden_res.json()["error"]["code"] == "FORBIDDEN_PLATFORM_ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_platform_admin_tenant_lifecycle_and_analytics(client):
    # Login as platform admin
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@platform.com", "password": "AdminPass123!"},
    )
    assert login_res.status_code == 200
    admin_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. List existing tenants
    list_res = await client.get("/api/v1/platform/tenants", headers=headers)
    assert list_res.status_code == 200
    tenants = list_res.json()["data"]
    assert len(tenants) >= 2
    assert any(t["slug"] == "apex-cinemas" for t in tenants)

    # 2. Onboard new tenant
    onboard_payload = {
        "name": "Nova Stellar Theaters",
        "slug": "nova-stellar",
        "admin_email": "admin@novastellar.com",
        "subscription_plan": "ENTERPRISE",
    }
    create_res = await client.post("/api/v1/platform/tenants", json=onboard_payload, headers=headers)
    assert create_res.status_code == 200
    new_tenant = create_res.json()["data"]
    assert new_tenant["name"] == "Nova Stellar Theaters"
    assert new_tenant["slug"] == "nova-stellar"
    assert new_tenant["status"] == "ACTIVE"
    tenant_id = new_tenant["id"]

    # 3. Duplicate slug fails
    dup_res = await client.post("/api/v1/platform/tenants", json=onboard_payload, headers=headers)
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "TENANT_SLUG_ALREADY_EXISTS"

    # 4. Update tenant status (suspend)
    patch_res = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/status",
        json={"status": "SUSPENDED", "reason": "Billing audit pending"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["status"] == "SUSPENDED"

    # 5. Query analytics
    analytics_res = await client.get("/api/v1/platform/analytics", headers=headers)
    assert analytics_res.status_code == 200
    analytics_data = analytics_res.json()["data"]
    assert analytics_data["total_tenants"] >= 3
    assert "gross_volume_minor" in analytics_data
    assert analytics_data["system_health"] == "HEALTHY"

    # 6. Query audit logs
    audit_res = await client.get("/api/v1/platform/audit-logs", headers=headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()["data"]
    assert len(logs) > 0
    assert any(log["action"] == "TENANT_ONBOARDED" for log in logs)


@pytest.mark.asyncio
async def test_customer_booking_history_and_cancellation(client):
    # Register customer
    customer_email = "customer.cancellation@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Customer",
            "email": customer_email,
            "password": "Password123!",
            "phone": "+1987654321",
        },
    )
    assert reg_res.status_code == 200

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": customer_email, "password": "Password123!"},
    )
    assert login_res.status_code == 200
    cust_token = login_res.json()["data"]["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # Hold seats and create booking
    show_id = "show-apex-cosmic-001"
    seat_label = "D1"
    seat_id = f"ss-{show_id}-d1"

    lock_res = await client.post(
        "/api/v1/seat-locks",
        json={
            "show_id": show_id,
            "show_seat_ids": [seat_id],
            "booking_session_id": "sess-cancel-test",
        },
        headers={"Idempotency-Key": "idemp-cancel-lock-d1"},
    )
    assert lock_res.status_code == 200
    hold_id = lock_res.json()["data"]["hold_id"]

    booking_res = await client.post(
        "/api/v1/bookings",
        json={
            "hold_id": hold_id,
            "customer_contact": {
                "email": customer_email,
                "phone": "+1987654321",
            },
        },
        headers={
            "Idempotency-Key": "idemp-cancel-book-d1",
            "Authorization": f"Bearer {cust_token}",
        },
    )
    assert booking_res.status_code == 200
    booking_id = booking_res.json()["data"]["id"]

    # Customer queries their bookings
    my_bookings_res = await client.get("/api/v1/bookings/me", headers=cust_headers)
    assert my_bookings_res.status_code == 200
    my_bookings = my_bookings_res.json()["data"]
    assert len(my_bookings) >= 1
    assert any(b["id"] == booking_id for b in my_bookings)

    # Customer cancels the booking
    cancel_res = await client.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        headers=cust_headers,
    )
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()["data"]
    assert cancel_data["status"] == "CANCELLED"
    assert "D1" in cancel_data["released_seats"]

    # Cancelling again fails
    cancel_again_res = await client.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        headers=cust_headers,
    )
    assert cancel_again_res.status_code == 400
    assert cancel_again_res.json()["error"]["code"] == "ALREADY_CANCELLED"
