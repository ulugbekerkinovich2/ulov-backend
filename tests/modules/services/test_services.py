"""Services API — intake, queue, transitions end-to-end."""

from __future__ import annotations

import pytest

from tests.modules.conftest import (
    _create_car,
    _create_center,
    _hdr,
)


def _customer_owns_car(api_client, customer_token, plate=None):
    if plate is None:
        return _create_car(api_client, customer_token)
    return _create_car(api_client, customer_token, plate=plate)


@pytest.mark.integration
def test_intake_creates_waiting_service(
    api_client, owner_token, customer_token
) -> None:
    center = _create_center(api_client, owner_token)
    car = _customer_owns_car(api_client, customer_token, plate="01A555AA")

    r = api_client.post(
        f"/api/v1/service-centers/{center['id']}/intakes",
        json={"plate": "01A555AA", "mileage_at_intake": 32000},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "waiting"
    assert body["car_id"] == car["id"]
    assert body["mileage_at_intake"] == 32000


@pytest.mark.integration
def test_create_service_rejects_mileage_regression(
    api_client, owner_token, customer_token
) -> None:
    center = _create_center(api_client, owner_token)
    car = _customer_owns_car(api_client, customer_token)
    r = api_client.post(
        f"/api/v1/service-centers/{center['id']}/services",
        json={"car_id": car["id"], "mileage_at_intake": 1},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SERVICE_MILEAGE_REGRESSION"


@pytest.mark.integration
def test_full_state_machine_round_trip(
    api_client, owner_token, customer_token, db
) -> None:
    center = _create_center(api_client, owner_token)
    _customer_owns_car(api_client, customer_token, plate="01B100CC")

    intake = api_client.post(
        f"/api/v1/service-centers/{center['id']}/intakes",
        json={"plate": "01B100CC", "mileage_at_intake": 40000},
        headers=_hdr(owner_token),
    ).json()
    sid = intake["id"]

    # waiting → in_progress
    r = api_client.post(
        f"/api/v1/services/{sid}/transition",
        json={"to_status": "in_progress"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "in_progress"
    assert r.json()["started_at"] is not None

    # in_progress → paused (with reason)
    r = api_client.post(
        f"/api/v1/services/{sid}/transition",
        json={"to_status": "paused", "reason": "waiting for parts"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "paused"
    assert r.json()["pause_reason"] == "waiting for parts"

    # paused → in_progress (resume)
    r = api_client.post(
        f"/api/v1/services/{sid}/transition",
        json={"to_status": "in_progress"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"

    # in_progress → completed
    r = api_client.post(
        f"/api/v1/services/{sid}/transition",
        json={"to_status": "completed"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert r.json()["completed_at"] is not None

    # Terminal — further transitions blocked
    r = api_client.post(
        f"/api/v1/services/{sid}/transition",
        json={"to_status": "in_progress"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SERVICE_STATE_TERMINAL"


@pytest.mark.integration
def test_cancel_requires_reason(
    api_client, owner_token, customer_token
) -> None:
    center = _create_center(api_client, owner_token)
    _customer_owns_car(api_client, customer_token, plate="01C111DD")
    intake = api_client.post(
        f"/api/v1/service-centers/{center['id']}/intakes",
        json={"plate": "01C111DD", "mileage_at_intake": 40000},
        headers=_hdr(owner_token),
    ).json()

    r = api_client.post(
        f"/api/v1/services/{intake['id']}/transition",
        json={"to_status": "cancelled"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SERVICE_CANCEL_REASON_REQUIRED"

    r = api_client.post(
        f"/api/v1/services/{intake['id']}/transition",
        json={"to_status": "cancelled", "reason": "customer changed mind"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


@pytest.mark.integration
def test_customer_can_view_only_own_service(
    api_client, owner_token, customer_token, db
) -> None:
    center = _create_center(api_client, owner_token)
    _customer_owns_car(api_client, customer_token, plate="01D200EE")
    intake = api_client.post(
        f"/api/v1/service-centers/{center['id']}/intakes",
        json={"plate": "01D200EE", "mileage_at_intake": 40000},
        headers=_hdr(owner_token),
    ).json()
    sid = intake["id"]

    # Owner of the car can read.
    r = api_client.get(f"/api/v1/services/{sid}", headers=_hdr(customer_token))
    assert r.status_code == 200

    # A different customer cannot.
    from tests.modules.conftest import _register

    other_token = _register(api_client, "+998905555555")
    r = api_client.get(f"/api/v1/services/{sid}", headers=_hdr(other_token))
    assert r.status_code == 403


@pytest.mark.integration
def test_timeline_grows_with_transitions(
    api_client, owner_token, customer_token
) -> None:
    center = _create_center(api_client, owner_token)
    _customer_owns_car(api_client, customer_token, plate="01E300FF")
    intake = api_client.post(
        f"/api/v1/service-centers/{center['id']}/intakes",
        json={"plate": "01E300FF", "mileage_at_intake": 40000},
        headers=_hdr(owner_token),
    ).json()
    sid = intake["id"]

    api_client.post(
        f"/api/v1/services/{sid}/transition",
        json={"to_status": "in_progress"},
        headers=_hdr(owner_token),
    )
    api_client.post(
        f"/api/v1/services/{sid}/transition",
        json={"to_status": "completed"},
        headers=_hdr(owner_token),
    )

    r = api_client.get(
        f"/api/v1/services/{sid}/timeline", headers=_hdr(owner_token)
    )
    assert r.status_code == 200
    timeline = r.json()
    assert [t["to_status"] for t in timeline] == [
        "waiting",
        "in_progress",
        "completed",
    ]


@pytest.mark.integration
def test_vehicle_lookup_by_plate(api_client, owner_token, customer_token) -> None:
    car = _customer_owns_car(api_client, customer_token, plate="01F400GG")
    r = api_client.get(
        "/api/v1/vehicles/lookup",
        params={"plate": "01F400GG"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["car_id"] == car["id"]


@pytest.mark.integration
def test_vehicle_lookup_404_when_missing(api_client, owner_token) -> None:
    r = api_client.get(
        "/api/v1/vehicles/lookup",
        params={"plate": "ZZ999ZZ"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "VEHICLE_NOT_FOUND"


@pytest.mark.integration
def test_condition_photo_via_upload_key(
    api_client, owner_token, customer_token
) -> None:
    """Server resolves an upload key into a public URL when attaching a photo."""
    center = _create_center(api_client, owner_token)
    _create_car(api_client, customer_token, plate="01H700XX")
    intake = api_client.post(
        f"/api/v1/service-centers/{center['id']}/intakes",
        json={"plate": "01H700XX", "mileage_at_intake": 40000},
        headers=_hdr(owner_token),
    ).json()

    key = "services/abc/test.jpg"
    r = api_client.post(
        f"/api/v1/services/{intake['id']}/condition-photos",
        json={"key": key, "stage": "before"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["stage"] == "before"
    assert key in body["url"]


@pytest.mark.integration
def test_condition_photo_requires_key_or_url(
    api_client, owner_token, customer_token
) -> None:
    center = _create_center(api_client, owner_token)
    _create_car(api_client, customer_token, plate="01H701YY")
    intake = api_client.post(
        f"/api/v1/service-centers/{center['id']}/intakes",
        json={"plate": "01H701YY", "mileage_at_intake": 40000},
        headers=_hdr(owner_token),
    ).json()

    r = api_client.post(
        f"/api/v1/services/{intake['id']}/condition-photos",
        json={"stage": "before"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 422


@pytest.mark.integration
def test_queue_filtering_by_status(api_client, owner_token, customer_token) -> None:
    center = _create_center(api_client, owner_token)
    _customer_owns_car(api_client, customer_token, plate="01G500HH")
    intake = api_client.post(
        f"/api/v1/service-centers/{center['id']}/intakes",
        json={"plate": "01G500HH", "mileage_at_intake": 40000},
        headers=_hdr(owner_token),
    ).json()
    api_client.post(
        f"/api/v1/services/{intake['id']}/transition",
        json={"to_status": "in_progress"},
        headers=_hdr(owner_token),
    )

    r = api_client.get(
        f"/api/v1/service-centers/{center['id']}/services",
        params={"status": "in_progress"},
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200
    assert all(s["status"] == "in_progress" for s in r.json())
    assert any(s["id"] == intake["id"] for s in r.json())
