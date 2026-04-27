"""Fuel station nearby search + fuel-type filter."""

from __future__ import annotations

import pytest

from app.modules.fuel_stations.models import FuelStation


def _add_station(db, name, lat, lng, prices):
    db.add(
        FuelStation(
            name=name,
            address="X",
            location={"lat": lat, "lng": lng},
            prices=prices,
        )
    )


@pytest.mark.integration
def test_nearby_returns_within_radius(api_client, db) -> None:
    _add_station(db, "Near", 41.31, 69.27, {"ai95": 13500})
    _add_station(db, "Far", 41.50, 69.50, {"ai95": 13500})
    db.flush()

    r = api_client.get(
        "/api/v1/fuel-stations",
        params={"lat": 41.31, "lng": 69.27, "radius_m": 2000, "limit": 10},
    )
    assert r.status_code == 200, r.text
    names = [s["name"] for s in r.json()]
    assert "Near" in names
    assert "Far" not in names


@pytest.mark.integration
def test_fuel_filter_excludes_missing(api_client, db) -> None:
    _add_station(db, "Petrol Only", 41.31, 69.27, {"ai95": 13500})
    _add_station(db, "Diesel Too", 41.311, 69.271, {"ai95": 13500, "diesel": 11000})
    db.flush()

    r = api_client.get(
        "/api/v1/fuel-stations",
        params={"lat": 41.31, "lng": 69.27, "radius_m": 5000, "fuel": "diesel"},
    )
    assert r.status_code == 200
    names = [s["name"] for s in r.json()]
    assert names == ["Diesel Too"]
