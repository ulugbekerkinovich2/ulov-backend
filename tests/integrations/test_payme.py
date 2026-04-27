"""Payme adapter — auth + JSON-RPC method dispatch."""

from __future__ import annotations

import base64
import os

import pytest

from app.modules.billing.models import Payment, SubscriptionPlan
from tests.modules.conftest import _create_center, _hdr


@pytest.fixture(autouse=True)
def _payme_env(monkeypatch):
    monkeypatch.setattr("app.config.settings.PAYME_SECRET", "merch-secret")
    monkeypatch.setattr("app.config.settings.PAYME_TEST_MODE", True)


def _basic(user: str, secret: str) -> str:
    raw = f"{user}:{secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _seed(db, owner_token, api_client, *, amount=15_000_000):
    db.add(
        SubscriptionPlan(
            code="basic", name="Basic", monthly_price=amount, duration_days=30
        )
    )
    db.flush()
    center = _create_center(api_client, owner_token)
    payment_id = api_client.post(
        "/api/v1/billing/checkout",
        json={
            "plan_code": "basic",
            "center_id": center["id"],
            "provider": "payme",
        },
        headers=_hdr(owner_token),
    ).json()["payment_id"]
    return payment_id, amount


@pytest.mark.integration
def test_payme_rejects_bad_basic_auth(api_client, db, owner_token) -> None:
    payment_id, amount = _seed(db, owner_token, api_client)
    body = {
        "id": 1,
        "method": "CheckPerformTransaction",
        "params": {"amount": amount, "account": {"payment_id": payment_id}},
    }
    r = api_client.post(
        "/api/v1/billing/webhooks/payme",
        json=body,
        headers={"Authorization": _basic("Paycom", "wrong")},
    )
    assert r.status_code == 200
    assert r.json()["error"]["code"] == -32504


@pytest.mark.integration
def test_payme_full_lifecycle(api_client, db, owner_token) -> None:
    payment_id, amount = _seed(db, owner_token, api_client)
    auth = {"Authorization": _basic("Paycom", "merch-secret")}

    # CheckPerformTransaction
    r = api_client.post(
        "/api/v1/billing/webhooks/payme",
        json={
            "id": 1,
            "method": "CheckPerformTransaction",
            "params": {"amount": amount, "account": {"payment_id": payment_id}},
        },
        headers=auth,
    )
    assert r.json() == {"id": 1, "result": {"allow": True}}

    # CreateTransaction
    r = api_client.post(
        "/api/v1/billing/webhooks/payme",
        json={
            "id": 2,
            "method": "CreateTransaction",
            "params": {
                "id": "PAYME-TXN-1",
                "time": 1735689600000,
                "amount": amount,
                "account": {"payment_id": payment_id},
            },
        },
        headers=auth,
    )
    assert r.json()["result"]["state"] == 1
    assert r.json()["result"]["transaction"] == payment_id

    # PerformTransaction
    r = api_client.post(
        "/api/v1/billing/webhooks/payme",
        json={
            "id": 3,
            "method": "PerformTransaction",
            "params": {"id": "PAYME-TXN-1", "time": 1735689700000},
        },
        headers=auth,
    )
    assert r.json()["result"]["state"] == 2

    # CheckTransaction echoes paid state
    r = api_client.post(
        "/api/v1/billing/webhooks/payme",
        json={
            "id": 4,
            "method": "CheckTransaction",
            "params": {"id": "PAYME-TXN-1"},
        },
        headers=auth,
    )
    assert r.json()["result"]["state"] == 2


@pytest.mark.integration
def test_payme_amount_mismatch(api_client, db, owner_token) -> None:
    payment_id, _ = _seed(db, owner_token, api_client, amount=10_000)
    auth = {"Authorization": _basic("Paycom", "merch-secret")}
    r = api_client.post(
        "/api/v1/billing/webhooks/payme",
        json={
            "id": 5,
            "method": "CheckPerformTransaction",
            "params": {"amount": 1, "account": {"payment_id": payment_id}},
        },
        headers=auth,
    )
    assert r.json()["error"]["code"] == -31001


@pytest.mark.integration
def test_payme_unknown_method(api_client, db, owner_token) -> None:
    auth = {"Authorization": _basic("Paycom", "merch-secret")}
    r = api_client.post(
        "/api/v1/billing/webhooks/payme",
        json={"id": 99, "method": "DoesNotExist", "params": {}},
        headers=auth,
    )
    assert r.json()["error"]["code"] == -31003
