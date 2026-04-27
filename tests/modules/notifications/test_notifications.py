"""Notifications inbox + device registration."""

from __future__ import annotations

import pytest

AUTH = "/api/v1/auth"
NOTIF = "/api/v1/notifications"
DEVICES = "/api/v1/devices"


def _register(api_client, phone: str = "+998901234567") -> tuple:
    resp = api_client.post(
        f"{AUTH}/register", json={"phone": phone, "password": "secret123"}
    )
    body = resp.json()
    return body["access_token"], body["user"]["id"]


def _hdr(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


@pytest.mark.integration
def test_empty_inbox(api_client) -> None:
    token, _ = _register(api_client)
    resp = api_client.get(NOTIF, headers=_hdr(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread_count"] == 0
    assert body["items"] == []


@pytest.mark.integration
def test_create_and_read_notification(api_client, db) -> None:
    from app.modules.notifications import service as notif_svc

    token, user_id = _register(api_client)
    notif_svc.create_notification(
        db,
        user_id=user_id,
        kind="service.completed",
        title="Your service is done",
        body="Pick up your car",
    )
    db.commit()

    resp = api_client.get(NOTIF, headers=_hdr(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread_count"] == 1
    assert len(body["items"]) == 1
    nid = body["items"][0]["id"]

    resp = api_client.post(f"{NOTIF}/{nid}/read", headers=_hdr(token))
    assert resp.status_code == 204

    body2 = api_client.get(NOTIF, headers=_hdr(token)).json()
    assert body2["unread_count"] == 0


@pytest.mark.integration
def test_mark_unknown_returns_404(api_client) -> None:
    token, _ = _register(api_client)
    resp = api_client.post(
        f"{NOTIF}/00000000-0000-0000-0000-000000000000/read",
        headers=_hdr(token),
    )
    assert resp.status_code == 404


@pytest.mark.integration
def test_device_registration_is_idempotent(api_client) -> None:
    token, _ = _register(api_client)
    payload = {"token": "fcm-token-abcdef-1234567890", "platform": "android"}
    resp1 = api_client.post(DEVICES, json=payload, headers=_hdr(token))
    assert resp1.status_code == 201
    # Registering the same token again returns the same row.
    resp2 = api_client.post(DEVICES, json=payload, headers=_hdr(token))
    assert resp2.status_code == 201
    assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.integration
def test_device_rejects_bad_platform(api_client) -> None:
    token, _ = _register(api_client)
    resp = api_client.post(
        DEVICES,
        json={"token": "fcm-token-abc123456", "platform": "windows"},
        headers=_hdr(token),
    )
    assert resp.status_code == 422
