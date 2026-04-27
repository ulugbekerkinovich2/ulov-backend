"""Reviews — create + list own + list by centre."""

from __future__ import annotations

import uuid

import pytest

AUTH = "/api/v1/auth"
REVIEWS = "/api/v1/reviews"


def _register(api_client, phone: str = "+998901234567") -> str:
    resp = api_client.post(
        f"{AUTH}/register", json={"phone": phone, "password": "secret123"}
    )
    return resp.json()["access_token"]


def _hdr(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


@pytest.mark.integration
def test_create_review_happy_path(api_client) -> None:
    token = _register(api_client)
    center_id = str(uuid.uuid4())
    resp = api_client.post(
        REVIEWS,
        json={"center_id": center_id, "rating": 5, "text": "Zo'r"},
        headers=_hdr(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["rating"] == 5
    assert body["text"] == "Zo'r"
    assert body["center_id"] == center_id


@pytest.mark.integration
def test_create_review_rejects_rating_out_of_range(api_client) -> None:
    token = _register(api_client)
    resp = api_client.post(
        REVIEWS,
        json={"center_id": str(uuid.uuid4()), "rating": 10},
        headers=_hdr(token),
    )
    assert resp.status_code == 422


@pytest.mark.integration
def test_list_my_reviews(api_client) -> None:
    token = _register(api_client)
    center = str(uuid.uuid4())
    for rating in (3, 4, 5):
        api_client.post(
            REVIEWS,
            json={"center_id": center, "rating": rating},
            headers=_hdr(token),
        )
    resp = api_client.get(f"{REVIEWS}/me", headers=_hdr(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3


@pytest.mark.integration
def test_list_center_reviews_is_public(api_client) -> None:
    token = _register(api_client)
    center = str(uuid.uuid4())
    api_client.post(
        REVIEWS,
        json={"center_id": center, "rating": 4, "text": "OK"},
        headers=_hdr(token),
    )
    # No auth header.
    resp = api_client.get(f"{REVIEWS}/center/{center}")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
