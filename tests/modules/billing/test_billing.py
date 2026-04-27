"""Billing — plans, checkout, idempotent webhooks."""

from __future__ import annotations

import pytest

from app.modules.billing.models import SubscriptionPlan
from tests.modules.conftest import _create_center, _hdr


def _seed_plan(db, code="basic", price=15_000_000, days=30):
    db.add(
        SubscriptionPlan(
            code=code,
            name="Basic plan",
            monthly_price=price,
            duration_days=days,
            active=True,
        )
    )
    db.flush()


@pytest.mark.integration
def test_plans_endpoint(api_client, db) -> None:
    _seed_plan(db)
    r = api_client.get("/api/v1/billing/plans")
    assert r.status_code == 200
    assert any(p["code"] == "basic" for p in r.json())


@pytest.mark.integration
def test_checkout_creates_pending_payment(
    api_client, db, owner_token
) -> None:
    _seed_plan(db)
    center = _create_center(api_client, owner_token)

    r = api_client.post(
        "/api/v1/billing/checkout",
        json={
            "plan_code": "basic",
            "center_id": center["id"],
            "provider": "manual",
        },
        headers=_hdr(owner_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["amount"] == 15_000_000
    assert "manual" in body["redirect_url"]


@pytest.mark.integration
def test_webhook_marks_paid_and_extends_subscription(
    api_client, db, owner_token
) -> None:
    _seed_plan(db, code="pro", price=25_000_000, days=30)
    center = _create_center(api_client, owner_token)

    payment_id = api_client.post(
        "/api/v1/billing/checkout",
        json={
            "plan_code": "pro",
            "center_id": center["id"],
            "provider": "payme",
        },
        headers=_hdr(owner_token),
    ).json()["payment_id"]

    r = api_client.post(
        "/api/v1/billing/webhooks/test",
        json={
            "payment_id": payment_id,
            "external_ref": "PAYME-ABC-001",
            "status": "paid",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paid"
    assert r.json()["paid_at"] is not None

    # Centre's subscription_until is bumped.
    r = api_client.get(
        f"/api/v1/service-centers/{center['id']}", headers=_hdr(owner_token)
    )
    assert r.json()["subscription_until"] is not None


@pytest.mark.integration
def test_webhook_idempotent_replay(api_client, db, owner_token) -> None:
    _seed_plan(db)
    center = _create_center(api_client, owner_token)
    payment_id = api_client.post(
        "/api/v1/billing/checkout",
        json={
            "plan_code": "basic",
            "center_id": center["id"],
            "provider": "click",
        },
        headers=_hdr(owner_token),
    ).json()["payment_id"]

    body = {
        "payment_id": payment_id,
        "external_ref": "CLICK-XYZ",
        "status": "paid",
    }
    first = api_client.post("/api/v1/billing/webhooks/test", json=body)
    second = api_client.post("/api/v1/billing/webhooks/test", json=body)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "paid"
    assert first.json()["paid_at"] == second.json()["paid_at"]


@pytest.mark.integration
def test_checkout_blocks_other_owners_centre(
    api_client, db, owner_token
) -> None:
    _seed_plan(db)
    center = _create_center(api_client, owner_token)
    from tests.modules.conftest import _make_user_with_role, _token

    other = _make_user_with_role(db, phone="+998919199881", role="owner")
    db.flush()
    other_token = _token(other.id, "owner")

    r = api_client.post(
        "/api/v1/billing/checkout",
        json={
            "plan_code": "basic",
            "center_id": center["id"],
            "provider": "manual",
        },
        headers=_hdr(other_token),
    )
    assert r.status_code == 403
