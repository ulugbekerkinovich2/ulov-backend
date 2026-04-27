"""OTP request + verify flows."""

from __future__ import annotations

import pytest

BASE = "/api/v1/auth"


@pytest.mark.integration
def test_otp_request_returns_dev_code(client) -> None:
    response = client.post(f"{BASE}/otp/request", json={"phone": "+998901234567"})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "sent"
    assert body["ttl_seconds"] > 0
    # Dev echo is enabled via the default test env — we receive the code.
    assert body["dev_code"] and len(body["dev_code"]) == 6


@pytest.mark.integration
def test_otp_verify_unknown_user_returns_404(client) -> None:
    phone = "+998901234567"
    resp = client.post(f"{BASE}/otp/request", json={"phone": phone})
    code = resp.json()["dev_code"]
    response = client.post(
        f"{BASE}/otp/verify", json={"phone": phone, "code": code}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUTH_USER_NOT_FOUND"


@pytest.mark.integration
def test_otp_verify_logs_in_existing_user(client) -> None:
    phone = "+998901234567"
    client.post(f"{BASE}/register", json={"phone": phone, "password": "secret123"})
    client.cookies.clear()

    code = client.post(f"{BASE}/otp/request", json={"phone": phone}).json()["dev_code"]
    response = client.post(
        f"{BASE}/otp/verify", json={"phone": phone, "code": code}
    )
    assert response.status_code == 200
    assert response.json()["user"]["phone"] == phone
    assert "ulov_refresh" in client.cookies


@pytest.mark.integration
def test_otp_verify_wrong_code_returns_401(client) -> None:
    phone = "+998901234567"
    client.post(f"{BASE}/register", json={"phone": phone, "password": "secret123"})
    client.post(f"{BASE}/otp/request", json={"phone": phone})
    response = client.post(
        f"{BASE}/otp/verify", json={"phone": phone, "code": "000000"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_OTP_INVALID"


@pytest.mark.integration
def test_otp_verify_expired_returns_401(client) -> None:
    phone = "+998901234567"
    client.post(f"{BASE}/register", json={"phone": phone, "password": "secret123"})
    # No request call — OTP simply does not exist.
    response = client.post(
        f"{BASE}/otp/verify", json={"phone": phone, "code": "123456"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_OTP_EXPIRED"


@pytest.mark.integration
def test_otp_locks_after_too_many_failures(client) -> None:
    phone = "+998901234567"
    client.post(f"{BASE}/register", json={"phone": phone, "password": "secret123"})
    client.post(f"{BASE}/otp/request", json={"phone": phone})
    # Default OTP_MAX_ATTEMPTS=5 → five wrong codes = lock
    for _ in range(5):
        client.post(f"{BASE}/otp/verify", json={"phone": phone, "code": "000000"})

    # The 5th attempt returns LOCKED (deletes the OTP and sets the lock).
    # A subsequent request for a new OTP should also be blocked.
    response = client.post(f"{BASE}/otp/request", json={"phone": phone})
    # Lock is a 401 for request too (our service raises UnauthorizedError).
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_OTP_LOCKED"
