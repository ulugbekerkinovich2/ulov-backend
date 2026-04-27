"""Service-centre CRUD + ownership."""

from __future__ import annotations

import pytest

from tests.modules.conftest import _create_center, _hdr


@pytest.mark.integration
def test_owner_can_create_and_list(api_client, owner_token) -> None:
    center = _create_center(api_client, owner_token, name="One")
    assert center["name"] == "One"

    r = api_client.get("/api/v1/service-centers", headers=_hdr(owner_token))
    assert r.status_code == 200
    assert any(c["id"] == center["id"] for c in r.json())


@pytest.mark.integration
def test_customer_cannot_create_centre(api_client, customer_token) -> None:
    r = api_client.post(
        "/api/v1/service-centers",
        json={"name": "X", "phone": "+998901111111", "address": "A"},
        headers=_hdr(customer_token),
    )
    assert r.status_code == 401


@pytest.mark.integration
def test_other_owner_cannot_patch(api_client, owner_token, db) -> None:
    center = _create_center(api_client, owner_token)

    # A second owner — different user.
    from tests.modules.conftest import _make_user_with_role, _token

    other = _make_user_with_role(db, phone="+998919999998", role="owner")
    db.flush()
    other_token = _token(other.id, "owner")

    r = api_client.patch(
        f"/api/v1/service-centers/{center['id']}",
        json={"name": "Hacked"},
        headers=_hdr(other_token),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CENTER_NOT_OWNER"


@pytest.mark.integration
def test_location_round_trips(api_client, owner_token) -> None:
    center = _create_center(
        api_client,
        owner_token,
        location={"lat": 41.31, "lng": 69.27},
    )
    r = api_client.get(
        f"/api/v1/service-centers/{center['id']}", headers=_hdr(owner_token)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["location"] is not None
    assert abs(body["location"]["lat"] - 41.31) < 1e-4
    assert abs(body["location"]["lng"] - 69.27) < 1e-4
