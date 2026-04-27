"""Shared helpers for Phase 3 tests.

Centralises customer/owner/mechanic creation + token minting so each test
module stays focussed on the behaviour under test.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.modules.users.models import User


AUTH = "/api/v1/auth"


def _register(api_client: TestClient, phone: str) -> str:
    r = api_client.post(
        f"{AUTH}/register",
        json={"phone": phone, "password": "secret123"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _make_user_with_role(
    db: Session, *, phone: str, role: str
) -> User:
    user = User(
        phone=phone,
        password_hash=hash_password("secret123"),
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def _token(user_id: str, role: str, *, center_id: Optional[str] = None) -> str:
    return create_access_token(
        subject=str(user_id), role=role, center_id=center_id
    )


def _hdr(t: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture()
def customer_token(api_client) -> str:
    return _register(api_client, f"+99890{uuid.uuid4().int % 10_000_000:07d}")


@pytest.fixture()
def owner(db) -> User:
    u = _make_user_with_role(
        db, phone=f"+99891{uuid.uuid4().int % 10_000_000:07d}", role="owner"
    )
    db.flush()
    return u


@pytest.fixture()
def owner_token(owner) -> str:
    return _token(owner.id, "owner")


@pytest.fixture()
def admin_token(db) -> str:
    u = _make_user_with_role(
        db, phone=f"+99895{uuid.uuid4().int % 10_000_000:07d}", role="admin"
    )
    db.flush()
    return _token(u.id, "admin")


def _create_center(api_client: TestClient, owner_token: str, **overrides: Any) -> dict:
    body = {
        "name": "Auto Service",
        "phone": "+998901234567",
        "address": "Tashkent",
        "services": ["oil_change", "brakes"],
    }
    body.update(overrides)
    r = api_client.post(
        "/api/v1/service-centers", json=body, headers=_hdr(owner_token)
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_car(api_client: TestClient, customer_token: str, **overrides: Any) -> dict:
    body = {
        "brand": "Chevrolet",
        "model": "Cobalt",
        "year": 2022,
        "plate": f"01A{uuid.uuid4().int % 1000:03d}BC",
        "mileage": 30000,
    }
    body.update(overrides)
    r = api_client.post("/api/v1/cars", json=body, headers=_hdr(customer_token))
    assert r.status_code == 201, r.text
    return r.json()


def _hire_mechanic(
    api_client: TestClient, owner_token: str, center_id: str
) -> Tuple[dict, str]:
    """Create mechanic via API + mint a mechanic token."""
    body = {
        "full_name": "Bob Mech",
        "login": f"bob{uuid.uuid4().hex[:6]}",
        "password": "secret123",
        "service_types": ["oil_change"],
    }
    r = api_client.post(
        f"/api/v1/service-centers/{center_id}/mechanics",
        json=body,
        headers=_hdr(owner_token),
    )
    assert r.status_code == 201, r.text
    mech = r.json()
    # Mechanics don't have a phone-user; tests issue a JWT with role=mechanic
    # bound to the centre. Use the mechanic's id as ``sub``.
    token = _token(mech["id"], "mechanic", center_id=center_id)
    return mech, token


# Re-export for tests
__all__ = (
    "AUTH",
    "_create_car",
    "_create_center",
    "_hdr",
    "_hire_mechanic",
    "_make_user_with_role",
    "_register",
    "_token",
    "admin_token",
    "customer_token",
    "owner",
    "owner_token",
)
