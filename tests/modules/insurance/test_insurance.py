"""Insurance — tariffs, quotes, policies."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.insurance.models import InsuranceTariff
from tests.modules.conftest import _create_car, _hdr


def _seed_tariff(db, code="osago", base=15_000_000):
    db.add(
        InsuranceTariff(
            code=code,
            name="OSAGO base",
            base_price=base,
            coefficients={
                "brand": {"Chevrolet": 1.1, "Lada": 0.9},
                "year_band": {"2020+": 1.2, "2015-2019": 1.0, "2010-2014": 0.85},
            },
            active=True,
        )
    )
    db.flush()


@pytest.mark.integration
def test_tariffs_endpoint_lists_active(api_client, db) -> None:
    _seed_tariff(db)
    r = api_client.get("/api/v1/insurance/tariffs")
    assert r.status_code == 200
    rows = r.json()
    assert any(t["code"] == "osago" for t in rows)


@pytest.mark.integration
def test_quote_applies_coefficients(api_client, db, customer_token) -> None:
    _seed_tariff(db)
    car = _create_car(api_client, customer_token, brand="Chevrolet", year=2022, plate="01I100AA")

    r = api_client.post(
        "/api/v1/insurance/quotes",
        json={"tariff_code": "osago", "car_id": car["id"]},
        headers=_hdr(customer_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # base 15_000_000 × 1.1 (Chevrolet) × 1.2 (2020+) = 19_800_000
    assert body["price"] == 19_800_000
    assert body["breakdown"]["brand_factor"] == 1.1
    assert body["breakdown"]["year_factor"] == 1.2


@pytest.mark.integration
def test_create_policy_pending(api_client, db, customer_token) -> None:
    _seed_tariff(db)
    car = _create_car(api_client, customer_token, plate="01I101BB")

    today = date.today()
    r = api_client.post(
        "/api/v1/insurance/policies",
        json={
            "tariff_code": "osago",
            "car_id": car["id"],
            "valid_from": today.isoformat(),
            "valid_to": (today + timedelta(days=365)).isoformat(),
        },
        headers=_hdr(customer_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # PolicyOut aliases payment_status → status; accept either shape so the
    # test survives further schema tweaks.
    assert body.get("payment_status", body.get("status")) == "pending"


@pytest.mark.integration
def test_invalid_date_range_422(api_client, db, customer_token) -> None:
    _seed_tariff(db)
    car = _create_car(api_client, customer_token, plate="01I102CC")
    today = date.today()
    r = api_client.post(
        "/api/v1/insurance/policies",
        json={
            "tariff_code": "osago",
            "car_id": car["id"],
            "valid_from": today.isoformat(),
            "valid_to": (today - timedelta(days=1)).isoformat(),
        },
        headers=_hdr(customer_token),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INSURANCE_DATE_RANGE_INVALID"


@pytest.mark.integration
def test_quote_for_other_users_car_blocked(api_client, db, customer_token) -> None:
    _seed_tariff(db)
    car = _create_car(api_client, customer_token, plate="01I103DD")

    from tests.modules.conftest import _register

    other = _register(api_client, "+998905554441")
    r = api_client.post(
        "/api/v1/insurance/quotes",
        json={"tariff_code": "osago", "car_id": car["id"]},
        headers=_hdr(other),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INSURANCE_CAR_NOT_OWNED"
