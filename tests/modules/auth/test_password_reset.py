"""Password reset flow — request OTP → confirm → old password dead."""

from __future__ import annotations

import pytest

BASE = "/api/v1/auth"


@pytest.mark.integration
def test_password_reset_happy_path(client) -> None:
    phone = "+998901234567"
    old_password = "initial-pass"
    new_password = "rotated-pass"

    client.post(
        f"{BASE}/register", json={"phone": phone, "password": old_password}
    )
    client.cookies.clear()

    # 1) Request reset OTP.
    resp = client.post(f"{BASE}/password/reset/request", json={"phone": phone})
    assert resp.status_code == 202
    code = resp.json()["dev_code"]
    assert code and len(code) == 6

    # 2) Confirm with new password.
    resp = client.post(
        f"{BASE}/password/reset/confirm",
        json={"phone": phone, "code": code, "new_password": new_password},
    )
    assert resp.status_code == 204

    # 3) Old password no longer works.
    resp = client.post(
        f"{BASE}/login", json={"phone": phone, "password": old_password}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"

    # 4) New password works.
    resp = client.post(
        f"{BASE}/login", json={"phone": phone, "password": new_password}
    )
    assert resp.status_code == 200


@pytest.mark.integration
def test_password_reset_request_hides_unknown_phone(client) -> None:
    """Endpoint must not leak whether the phone exists."""
    resp = client.post(
        f"{BASE}/password/reset/request", json={"phone": "+998901112233"}
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "sent"
    # But no OTP is actually issued — dev_code is None.
    assert body["dev_code"] is None


@pytest.mark.integration
def test_password_reset_confirm_bad_code_returns_401(client) -> None:
    phone = "+998901234567"
    client.post(f"{BASE}/register", json={"phone": phone, "password": "secret123"})
    client.post(f"{BASE}/password/reset/request", json={"phone": phone})

    resp = client.post(
        f"{BASE}/password/reset/confirm",
        json={"phone": phone, "code": "000000", "new_password": "new-one"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_OTP_INVALID"


@pytest.mark.integration
def test_password_reset_invalidates_existing_refresh(client) -> None:
    phone = "+998901234567"
    client.post(f"{BASE}/register", json={"phone": phone, "password": "secret123"})
    # Capture the refresh cookie issued on register.
    old_refresh = client.cookies["ulov_refresh"]

    code = client.post(
        f"{BASE}/password/reset/request", json={"phone": phone}
    ).json()["dev_code"]
    client.post(
        f"{BASE}/password/reset/confirm",
        json={"phone": phone, "code": code, "new_password": "brand-new"},
    )

    # Replay the pre-reset refresh → must be rejected.
    client.cookies.clear()
    client.cookies.set(
        "ulov_refresh", old_refresh, domain="testserver", path="/api/v1/auth"
    )
    resp = client.post(f"{BASE}/refresh")
    assert resp.status_code == 401
