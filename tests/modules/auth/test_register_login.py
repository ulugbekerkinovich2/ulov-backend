"""Register + login flows."""

from __future__ import annotations

import pytest

BASE = "/api/v1/auth"


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_register_returns_tokens_and_sets_cookie(client) -> None:
    response = client.post(
        f"{BASE}/register",
        json={
            "phone": "+998901234567",
            "password": "secret123",
            "full_name": "Test User",
            "city": "Tashkent",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["user"]["phone"] == "+998901234567"
    assert body["user"]["role"] == "customer"
    # Cookie is set (httpOnly, so TestClient still receives it in cookies).
    assert "ulov_refresh" in client.cookies
    assert len(client.cookies["ulov_refresh"]) > 20


@pytest.mark.integration
def test_register_duplicate_phone_returns_409(client) -> None:
    payload = {"phone": "+998901234567", "password": "secret123"}
    assert client.post(f"{BASE}/register", json=payload).status_code == 201
    response = client.post(f"{BASE}/register", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AUTH_PHONE_TAKEN"


def test_register_rejects_invalid_phone(client) -> None:
    response = client.post(
        f"{BASE}/register",
        json={"phone": "not-a-phone", "password": "secret123"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION"


def test_register_rejects_short_password(client) -> None:
    response = client.post(
        f"{BASE}/register",
        json={"phone": "+998901234567", "password": "abc"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_login_succeeds_after_register(client) -> None:
    phone = "+998901112233"
    client.post(f"{BASE}/register", json={"phone": phone, "password": "secret123"})
    # Clear the cookie we picked up from /register so /login sets its own.
    client.cookies.clear()

    response = client.post(
        f"{BASE}/login", json={"phone": phone, "password": "secret123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["phone"] == phone
    assert "ulov_refresh" in client.cookies


@pytest.mark.integration
def test_login_wrong_password_returns_401(client) -> None:
    phone = "+998901112233"
    client.post(f"{BASE}/register", json={"phone": phone, "password": "secret123"})
    response = client.post(
        f"{BASE}/login", json={"phone": phone, "password": "wrong-pass"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.integration
def test_login_unknown_phone_returns_401(client) -> None:
    response = client.post(
        f"{BASE}/login",
        json={"phone": "+998909999999", "password": "doesntmatter"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
