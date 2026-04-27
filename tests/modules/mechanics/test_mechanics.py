"""Mechanics CRUD + soft-delete + login uniqueness."""

from __future__ import annotations

import pytest

from tests.modules.conftest import _create_center, _hdr, _hire_mechanic


@pytest.mark.integration
def test_owner_creates_and_lists_mechanics(api_client, owner_token) -> None:
    center = _create_center(api_client, owner_token)
    mech, _t = _hire_mechanic(api_client, owner_token, center["id"])

    r = api_client.get(
        f"/api/v1/service-centers/{center['id']}/mechanics",
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()]
    assert mech["id"] in ids


@pytest.mark.integration
def test_login_uniqueness(api_client, owner_token) -> None:
    center = _create_center(api_client, owner_token)
    mech, _t = _hire_mechanic(api_client, owner_token, center["id"])

    r = api_client.post(
        f"/api/v1/service-centers/{center['id']}/mechanics",
        json={
            "full_name": "Dup",
            "login": mech["login"],
            "password": "secret123",
        },
        headers=_hdr(owner_token),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "MECHANIC_LOGIN_DUPLICATE"


@pytest.mark.integration
def test_soft_delete_excludes_from_list(api_client, owner_token) -> None:
    center = _create_center(api_client, owner_token)
    mech, _t = _hire_mechanic(api_client, owner_token, center["id"])

    r = api_client.delete(
        f"/api/v1/mechanics/{mech['id']}", headers=_hdr(owner_token)
    )
    assert r.status_code == 204

    r = api_client.get(
        f"/api/v1/service-centers/{center['id']}/mechanics",
        headers=_hdr(owner_token),
    )
    assert all(m["id"] != mech["id"] for m in r.json())
