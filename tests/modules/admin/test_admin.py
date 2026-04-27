"""Admin — platform-wide overview, user role flips, gating."""

from __future__ import annotations

import pytest

from tests.modules.conftest import _create_center, _hdr


@pytest.mark.integration
def test_overview_admin_only(
    api_client, admin_token, owner_token, customer_token
) -> None:
    r = api_client.get("/api/v1/admin/overview", headers=_hdr(customer_token))
    assert r.status_code == 403

    r = api_client.get("/api/v1/admin/overview", headers=_hdr(owner_token))
    assert r.status_code == 403

    r = api_client.get("/api/v1/admin/overview", headers=_hdr(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "users" in body
    assert "centres" in body
    assert "active_services" in body


@pytest.mark.integration
def test_list_users_filterable(
    api_client, admin_token, owner_token, customer_token
) -> None:
    r = api_client.get(
        "/api/v1/admin/users",
        params={"role": "owner"},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200
    rows = r.json()
    assert all(u["role"] == "owner" for u in rows)


@pytest.mark.integration
def test_change_role_records_audit(
    api_client, admin_token, customer_token, db
) -> None:
    # The customer fixture registered a user; flip them to owner.
    from app.modules.users.models import User
    from sqlalchemy import select

    # Fetch the most-recent customer.
    user = db.execute(
        select(User).where(User.role == "customer").order_by(User.created_at.desc())
    ).scalars().first()
    assert user is not None

    r = api_client.post(
        f"/api/v1/admin/users/{user.id}/role",
        json={"role": "owner"},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "owner"

    # Audit row exists.
    r = api_client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "user", "entity_id": str(user.id)},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200
    rows = r.json()
    assert any(row["action"] == "user.role_changed" for row in rows)


@pytest.mark.integration
def test_list_centres_visible_to_admin(api_client, admin_token, owner_token) -> None:
    _create_center(api_client, owner_token, name="Visible centre")
    r = api_client.get("/api/v1/admin/service-centers", headers=_hdr(admin_token))
    assert r.status_code == 200
    assert any(c["name"] == "Visible centre" for c in r.json())
