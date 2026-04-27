"""/me read + patch + avatar (stub)."""

from __future__ import annotations

import pytest

AUTH = "/api/v1/auth"
ME = "/api/v1/me"


def _register(client, phone: str = "+998901234567") -> str:
    resp = client.post(
        f"{AUTH}/register", json={"phone": phone, "password": "secret123"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_get_me_returns_current_user(api_client) -> None:
    token = _register(api_client)
    resp = api_client.get(ME, headers=_auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["phone"] == "+998901234567"
    assert body["role"] == "customer"


@pytest.mark.integration
def test_patch_me_updates_fields(api_client) -> None:
    token = _register(api_client)
    resp = api_client.patch(
        ME,
        json={"full_name": "Sardor", "city": "Toshkent", "email": "s@ulov.uz"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "Sardor"
    assert body["city"] == "Toshkent"
    assert body["email"] == "s@ulov.uz"


@pytest.mark.integration
def test_patch_me_rejects_bad_email(api_client) -> None:
    token = _register(api_client)
    resp = api_client.patch(
        ME, json={"email": "not-an-email"}, headers=_auth_header(token)
    )
    assert resp.status_code == 422


@pytest.mark.integration
def test_me_requires_auth(api_client) -> None:
    resp = api_client.get(ME)
    assert resp.status_code == 401


@pytest.mark.integration
def test_set_avatar_stub_updates_url(api_client) -> None:
    token = _register(api_client)
    resp = api_client.post(
        f"{ME}/avatar",
        json={"avatar_url": "https://cdn.ulov.uz/a/1.jpg"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["avatar_url"] == "https://cdn.ulov.uz/a/1.jpg"
