import pytest


@pytest.mark.asyncio
async def test_full_booking_and_payment_flow(client):
    show_id = "show-apex-cosmic-001"

    # 1. User locks seats B1 and B2
    lock_payload = {
        "show_id": show_id,
        "show_seat_ids": [f"ss-{show_id}-b1", f"ss-{show_id}-b2"],
        "booking_session_id": "sess-user-alpha-1",
    }
    lock_res = await client.post(
        "/api/v1/seat-locks",
        json=lock_payload,
        headers={"Idempotency-Key": "idemp-lock-b1b2"},
    )
    assert lock_res.status_code == 200
    hold_data = lock_res.json()["data"]
    hold_id = hold_data["hold_id"]
    assert hold_data["status"] == "HELD"

    # 2. Convert hold into PENDING booking
    booking_payload = {
        "hold_id": hold_id,
        "customer_contact": {
            "email": "customer.alpha@example.com",
            "phone": "+1234567890",
        },
    }
    book_res = await client.post(
        "/api/v1/bookings",
        json=booking_payload,
        headers={"Idempotency-Key": "idemp-book-b1b2"},
    )
    assert book_res.status_code == 200
    book_data = book_res.json()["data"]
    booking_id = book_data["id"]
    assert book_data["status"] == "PENDING"
    assert len(book_data["items"]) == 2
    # B1 (1800) + B2 (1800) = 3600 minor units ($36.00)
    assert book_data["total_minor"] == 3600
    assert "CIN-2026-" in book_data["booking_reference"]

    # 3. Initiate payment
    init_res = await client.post(
        "/api/v1/payments/initiate",
        json={"booking_id": booking_id, "provider": "mock"},
        headers={"Idempotency-Key": "idemp-pay-init-01"},
    )
    assert init_res.status_code == 200
    pay_data = init_res.json()["data"]
    assert pay_data["amount_minor"] == 3600
    assert pay_data["status"] == "PENDING"

    # 4. Webhook callback arrives confirming payment
    webhook_payload = {
        "event_id": "evt-mock-pay-success-01",
        "event_type": "payment_intent.succeeded",
        "provider": "mock",
        "payment_id": pay_data["payment_id"],
        "booking_id": booking_id,
        "amount_minor": 3600,
        "signature": "sig_valid_mock_signature_abc123",
    }
    hook_res = await client.post("/api/v1/payments/webhooks/mock", json=webhook_payload)
    assert hook_res.status_code == 200
    assert hook_res.json()["data"]["status"] == "CONFIRMED"

    # 5. Verify booking is now CONFIRMED
    detail_res = await client.get(f"/api/v1/bookings/{booking_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["data"]["status"] == "CONFIRMED"
    assert detail_res.json()["data"]["confirmed_at"] is not None

    # 6. Verify seats are now CONFIRMED in seat-map
    seatmap_res = await client.get(f"/api/v1/shows/{show_id}/seat-map")
    seats = seatmap_res.json()["data"]["seats"]
    seat_b1 = next(s for s in seats if s["label"] == "B1")
    assert seat_b1["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_duplicate_seat_locking_conflict_rejected(client):
    show_id = "show-apex-cosmic-001"

    # First user locks seat C1
    res1 = await client.post(
        "/api/v1/seat-locks",
        json={"show_id": show_id, "show_seat_ids": [f"ss-{show_id}-c1"], "booking_session_id": "sess-user-1"},
        headers={"Idempotency-Key": "idemp-user1-c1"},
    )
    assert res1.status_code == 200

    # Second user attempts to lock C1 concurrently
    res2 = await client.post(
        "/api/v1/seat-locks",
        json={"show_id": show_id, "show_seat_ids": [f"ss-{show_id}-c1"], "booking_session_id": "sess-user-2"},
        headers={"Idempotency-Key": "idemp-user2-c1"},
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "SEAT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_seat_hold_release(client):
    show_id = "show-apex-cosmic-001"

    # Lock seat C2
    res_lock = await client.post(
        "/api/v1/seat-locks",
        json={"show_id": show_id, "show_seat_ids": [f"ss-{show_id}-c2"], "booking_session_id": "sess-release-test"},
        headers={"Idempotency-Key": "idemp-lock-c2"},
    )
    assert res_lock.status_code == 200
    hold_id = res_lock.json()["data"]["hold_id"]

    # Customer releases seat
    res_release = await client.delete(f"/api/v1/seat-locks/{hold_id}")
    assert res_release.status_code == 200
    assert res_release.json()["data"]["status"] == "RELEASED"

    # Now another customer can lock seat C2 successfully
    res_relock = await client.post(
        "/api/v1/seat-locks",
        json={"show_id": show_id, "show_seat_ids": [f"ss-{show_id}-c2"], "booking_session_id": "sess-new-customer"},
        headers={"Idempotency-Key": "idemp-relock-c2"},
    )
    assert res_relock.status_code == 200
    assert res_relock.json()["data"]["status"] == "HELD"


@pytest.mark.asyncio
async def test_webhook_replay_protection(client):
    show_id = "show-apex-cosmic-001"

    # Create a hold & booking first
    lock_res = await client.post(
        "/api/v1/seat-locks",
        json={"show_id": show_id, "show_seat_ids": [f"ss-{show_id}-c3"], "booking_session_id": "sess-replay"},
        headers={"Idempotency-Key": "idemp-replay-c3"},
    )
    hold_id = lock_res.json()["data"]["hold_id"]

    book_res = await client.post(
        "/api/v1/bookings",
        json={"hold_id": hold_id, "customer_contact": {"email": "replay@example.com"}},
        headers={"Idempotency-Key": "idemp-replay-book"},
    )
    booking_id = book_res.json()["data"]["id"]

    webhook_payload = {
        "event_id": "evt-duplicate-replay-test-01",
        "event_type": "payment_intent.succeeded",
        "provider": "mock",
        "payment_id": "pay-mock-01",
        "booking_id": booking_id,
        "amount_minor": 1800,
        "signature": "sig_valid_sig",
    }
    # 1. First delivery
    res1 = await client.post("/api/v1/payments/webhooks/mock", json=webhook_payload)
    assert res1.status_code == 200
    assert res1.json()["data"]["status"] == "CONFIRMED"

    # 2. Duplicate delivery (replay)
    res2 = await client.post("/api/v1/payments/webhooks/mock", json=webhook_payload)
    assert res2.status_code == 200
    assert res2.json()["data"]["status"] == "ALREADY_PROCESSED"


@pytest.mark.asyncio
async def test_webhook_missing_signature_rejected(client):
    webhook_payload = {
        "event_id": "evt-nosig",
        "event_type": "payment_intent.succeeded",
        "provider": "mock",
        "payment_id": "pay-mock-02",
        "booking_id": "bk-fake",
        "amount_minor": 1800,
        "signature": "",  # Empty signature
    }
    res = await client.post("/api/v1/payments/webhooks/mock", json=webhook_payload)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_SIGNATURE"
