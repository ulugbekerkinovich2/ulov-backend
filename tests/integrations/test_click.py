"""Click adapter — md5 signature + prepare/complete dispatch."""

from __future__ import annotations

import hashlib

import pytest

from app.modules.billing.models import SubscriptionPlan
from tests.modules.conftest import _create_center, _hdr


SECRET = "click-secret"


@pytest.fixture(autouse=True)
def _click_env(monkeypatch):
    monkeypatch.setattr("app.config.settings.CLICK_SECRET_KEY", SECRET)
    monkeypatch.setattr("app.config.settings.CLICK_SERVICE_ID", "12345")
    monkeypatch.setattr("app.config.settings.CLICK_MERCHANT_ID", "merch-1")


def _seed(db, owner_token, api_client):
    db.add(
        SubscriptionPlan(
            code="basic", name="Basic", monthly_price=1_500_000, duration_days=30
        )
    )
    db.flush()
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
    return payment_id


def _sign(parts) -> str:
    return hashlib.md5("".join(str(p) for p in parts).encode("utf-8")).hexdigest()


@pytest.mark.integration
def test_click_prepare_and_complete(api_client, db, owner_token) -> None:
    payment_id = _seed(db, owner_token, api_client)

    # Prepare
    sign = _sign(
        ["abc-1", "12345", SECRET, payment_id, 15000, 0, "ts-1"]
    )
    r = api_client.post(
        "/api/v1/billing/webhooks/click",
        data={
            "click_trans_id": "abc-1",
            "service_id": "12345",
            "merchant_trans_id": payment_id,
            "amount": 15000,
            "action": 0,
            "sign_time": "ts-1",
            "sign_string": sign,
        },
    )
    body = r.json()
    assert r.status_code == 200
    assert body["error"] == 0
    prepare_id = body["merchant_prepare_id"]

    # Complete
    sign = _sign(
        ["abc-1", "12345", SECRET, payment_id, prepare_id, 15000, 1, "ts-2"]
    )
    r = api_client.post(
        "/api/v1/billing/webhooks/click",
        data={
            "click_trans_id": "abc-1",
            "service_id": "12345",
            "merchant_trans_id": payment_id,
            "merchant_prepare_id": prepare_id,
            "amount": 15000,
            "action": 1,
            "error": 0,
            "sign_time": "ts-2",
            "sign_string": sign,
        },
    )
    body = r.json()
    assert body["error"] == 0


@pytest.mark.integration
def test_click_bad_signature(api_client, db, owner_token) -> None:
    payment_id = _seed(db, owner_token, api_client)
    r = api_client.post(
        "/api/v1/billing/webhooks/click",
        data={
            "click_trans_id": "abc-2",
            "service_id": "12345",
            "merchant_trans_id": payment_id,
            "amount": 15000,
            "action": 0,
            "sign_time": "ts",
            "sign_string": "deadbeef",
        },
    )
    assert r.json()["error"] == -1


@pytest.mark.integration
def test_click_amount_mismatch(api_client, db, owner_token) -> None:
    payment_id = _seed(db, owner_token, api_client)
    sign = _sign(["abc-3", "12345", SECRET, payment_id, 9999, 0, "ts"])
    r = api_client.post(
        "/api/v1/billing/webhooks/click",
        data={
            "click_trans_id": "abc-3",
            "service_id": "12345",
            "merchant_trans_id": payment_id,
            "amount": 9999,
            "action": 0,
            "sign_time": "ts",
            "sign_string": sign,
        },
    )
    assert r.json()["error"] == -2
