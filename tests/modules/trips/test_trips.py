"""Trip lifecycle: start → points → finish."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.modules.conftest import _hdr


TRIPS = "/api/v1/trips"


@pytest.mark.integration
def test_full_trip_lifecycle(api_client, customer_token) -> None:
    # Start
    r = api_client.post(TRIPS, json={}, headers=_hdr(customer_token))
    assert r.status_code == 201, r.text
    trip = r.json()
    assert trip["finished_at"] is None
    sid = trip["id"]

    # Append points (Toshkent → Chilanzar — small displacement)
    base = datetime.now(tz=timezone.utc)
    pts = [
        {"lat": 41.3111, "lng": 69.2797, "ts": base.isoformat()},
        {
            "lat": 41.3120,
            "lng": 69.2810,
            "ts": (base + timedelta(seconds=30)).isoformat(),
        },
        {
            "lat": 41.3140,
            "lng": 69.2850,
            "ts": (base + timedelta(seconds=120)).isoformat(),
        },
    ]
    r = api_client.post(
        f"{TRIPS}/{sid}/points",
        json={"points": pts},
        headers=_hdr(customer_token),
    )
    assert r.status_code == 200
    assert r.json()["appended"] == 3

    # Finish
    r = api_client.post(f"{TRIPS}/{sid}/finish", headers=_hdr(customer_token))
    assert r.status_code == 200
    body = r.json()
    assert body["finished_at"] is not None
    assert float(body["distance_km"]) > 0
    assert body["duration_s"] >= 0


@pytest.mark.integration
def test_appending_to_finished_trip_409(api_client, customer_token) -> None:
    sid = api_client.post(TRIPS, json={}, headers=_hdr(customer_token)).json()["id"]
    api_client.post(f"{TRIPS}/{sid}/finish", headers=_hdr(customer_token))
    r = api_client.post(
        f"{TRIPS}/{sid}/points",
        json={"points": [{"lat": 41.0, "lng": 69.0}]},
        headers=_hdr(customer_token),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "TRIP_FINISHED"


@pytest.mark.integration
def test_other_users_trip_403(api_client, customer_token) -> None:
    sid = api_client.post(TRIPS, json={}, headers=_hdr(customer_token)).json()["id"]
    from tests.modules.conftest import _register

    other = _register(api_client, "+998905544332")
    r = api_client.post(
        f"{TRIPS}/{sid}/points",
        json={"points": [{"lat": 41.0, "lng": 69.0}]},
        headers=_hdr(other),
    )
    assert r.status_code == 403
