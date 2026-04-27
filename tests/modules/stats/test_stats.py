"""Stats — owner dashboard KPIs."""

from __future__ import annotations

import pytest

from tests.modules.conftest import _create_car, _create_center, _hdr


def _intake(api_client, owner_token, center_id, plate):
    return api_client.post(
        f"/api/v1/service-centers/{center_id}/intakes",
        json={"plate": plate, "mileage_at_intake": 40000},
        headers=_hdr(owner_token),
    ).json()


def _transition(api_client, owner_token, sid, to_status, reason=None):
    body = {"to_status": to_status}
    if reason:
        body["reason"] = reason
    return api_client.post(
        f"/api/v1/services/{sid}/transition",
        json=body,
        headers=_hdr(owner_token),
    )


@pytest.mark.integration
def test_overview_counts_by_status(api_client, owner_token, customer_token) -> None:
    center = _create_center(api_client, owner_token)
    for plate in ("01S100AA", "01S101BB", "01S102CC"):
        _create_car(api_client, customer_token, plate=plate)
        _intake(api_client, owner_token, center["id"], plate)

    # Move one to in_progress, one to completed.
    services = api_client.get(
        f"/api/v1/service-centers/{center['id']}/services",
        headers=_hdr(owner_token),
    ).json()
    _transition(api_client, owner_token, services[0]["id"], "in_progress")
    _transition(api_client, owner_token, services[1]["id"], "in_progress")
    _transition(api_client, owner_token, services[1]["id"], "completed")

    r = api_client.get(
        f"/api/v1/service-centers/{center['id']}/stats/overview",
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["by_status"]["waiting"] == 1
    assert body["by_status"]["in_progress"] == 1
    assert body["by_status"]["completed"] == 1
    assert body["queue"] == 2  # waiting + in_progress
    assert body["today_intakes"] == 3


@pytest.mark.integration
def test_revenue_sums_completed_services(
    api_client, owner_token, customer_token
) -> None:
    center = _create_center(api_client, owner_token)
    _create_car(api_client, customer_token, plate="01S200AA")
    intake = _intake(api_client, owner_token, center["id"], "01S200AA")

    # Add items + complete.
    api_client.patch(
        f"/api/v1/services/{intake['id']}",
        json={
            "items": [
                {
                    "service_type": "oil_change",
                    "service_price": 5000,
                    "parts_price": 12000,
                    "parts": [],
                }
            ]
        },
        headers=_hdr(owner_token),
    )
    _transition(api_client, owner_token, intake["id"], "in_progress")
    _transition(api_client, owner_token, intake["id"], "completed")

    r = api_client.get(
        f"/api/v1/service-centers/{center['id']}/stats/revenue",
        headers=_hdr(owner_token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 17000
    assert any(d["amount"] == 17000 for d in body["daily"])


@pytest.mark.integration
def test_other_owner_cannot_view_stats(api_client, owner_token, db) -> None:
    center = _create_center(api_client, owner_token)
    from tests.modules.conftest import _make_user_with_role, _token

    other = _make_user_with_role(db, phone="+998919199771", role="owner")
    db.flush()
    other_token = _token(other.id, "owner")

    r = api_client.get(
        f"/api/v1/service-centers/{center['id']}/stats/overview",
        headers=_hdr(other_token),
    )
    assert r.status_code == 403
