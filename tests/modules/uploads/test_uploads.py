"""Uploads — presign + confirm flow.

We stub the boto3 client because we don't want to talk to live R2 from CI.
Authorization rules are the interesting part to cover.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.modules.conftest import _create_car, _create_center, _hdr


PRESIGN = "/api/v1/uploads/presign"
CONFIRM = "/api/v1/uploads/confirm"


class _StubS3:
    def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):  # noqa: N803
        return f"https://stub-s3.example/{Params['Bucket']}/{Params['Key']}?sig=stub"


@pytest.fixture(autouse=True)
def _stub_s3():
    with patch(
        "app.modules.uploads.service.get_s3_client", return_value=_StubS3()
    ):
        yield


@pytest.mark.integration
def test_avatar_presign_and_confirm(api_client, customer_token) -> None:
    body = {
        "kind": "avatar",
        "content_type": "image/jpeg",
        "size_bytes": 12345,
        "filename": "me.jpg",
    }
    r = api_client.post(PRESIGN, json=body, headers=_hdr(customer_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["method"] == "PUT"
    assert data["upload_url"].startswith("https://stub-s3.example/")
    assert data["public_url"].startswith("https://")
    assert data["key"].startswith("avatars/")

    r = api_client.post(
        CONFIRM,
        json={"kind": "avatar", "key": data["key"]},
        headers=_hdr(customer_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["public_url"] == data["public_url"]


@pytest.mark.integration
def test_rejects_unsupported_content_type(api_client, customer_token) -> None:
    r = api_client.post(
        PRESIGN,
        json={
            "kind": "avatar",
            "content_type": "application/zip",
            "size_bytes": 1,
        },
        headers=_hdr(customer_token),
    )
    assert r.status_code == 422


@pytest.mark.integration
def test_rejects_oversize(api_client, customer_token) -> None:
    r = api_client.post(
        PRESIGN,
        json={
            "kind": "avatar",
            "content_type": "image/jpeg",
            "size_bytes": 999_999_999,
        },
        headers=_hdr(customer_token),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "UPLOAD_TOO_LARGE"


@pytest.mark.integration
def test_car_photo_requires_ownership(api_client, customer_token) -> None:
    car = _create_car(api_client, customer_token, plate="01U900AA")

    # Owner of the car can presign.
    r = api_client.post(
        PRESIGN,
        json={
            "kind": "car_photo",
            "content_type": "image/png",
            "size_bytes": 1024,
            "entity_id": car["id"],
        },
        headers=_hdr(customer_token),
    )
    assert r.status_code == 200, r.text
    key = r.json()["key"]
    assert key.startswith(f"cars/{car['id']}/")

    # A different customer is forbidden.
    from tests.modules.conftest import _register

    other = _register(api_client, "+998905554443")
    r = api_client.post(
        PRESIGN,
        json={
            "kind": "car_photo",
            "content_type": "image/png",
            "size_bytes": 1024,
            "entity_id": car["id"],
        },
        headers=_hdr(other),
    )
    assert r.status_code == 403


@pytest.mark.integration
def test_center_avatar_requires_owner(api_client, owner_token) -> None:
    center = _create_center(api_client, owner_token)
    r = api_client.post(
        PRESIGN,
        json={
            "kind": "center_avatar",
            "content_type": "image/jpeg",
            "size_bytes": 4096,
            "entity_id": center["id"],
        },
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200
    assert r.json()["key"].startswith(f"centers/{center['id']}/")


@pytest.mark.integration
def test_service_photo_requires_staff(api_client, customer_token, owner_token) -> None:
    # Customer cannot presign service photos.
    r = api_client.post(
        PRESIGN,
        json={
            "kind": "service_photo",
            "content_type": "image/jpeg",
            "size_bytes": 1000,
        },
        headers=_hdr(customer_token),
    )
    assert r.status_code == 403

    # Owner (staff) can.
    r = api_client.post(
        PRESIGN,
        json={
            "kind": "service_photo",
            "content_type": "image/jpeg",
            "size_bytes": 1000,
        },
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200
    assert r.json()["key"].startswith("services/")


@pytest.mark.integration
def test_confirm_writes_public_url_to_car(
    api_client, customer_token
) -> None:
    car = _create_car(api_client, customer_token, plate="01U901BB")
    presign = api_client.post(
        PRESIGN,
        json={
            "kind": "car_photo",
            "content_type": "image/png",
            "size_bytes": 1024,
            "entity_id": car["id"],
        },
        headers=_hdr(customer_token),
    ).json()

    r = api_client.post(
        CONFIRM,
        json={
            "kind": "car_photo",
            "key": presign["key"],
            "entity_id": car["id"],
        },
        headers=_hdr(customer_token),
    )
    assert r.status_code == 200

    # Verify the URL was persisted on the car row.
    r = api_client.get(f"/api/v1/cars/{car['id']}", headers=_hdr(customer_token))
    assert r.status_code == 200
    assert r.json()["photo_url"] == presign["public_url"]
