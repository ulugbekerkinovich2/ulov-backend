"""Cars CRUD + mileage + recommendations."""

from __future__ import annotations

import pytest

AUTH = "/api/v1/auth"
CARS = "/api/v1/cars"


def _register(api_client, phone: str = "+998901234567") -> str:
    resp = api_client.post(
        f"{AUTH}/register", json={"phone": phone, "password": "secret123"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _hdr(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _default_car() -> dict:
    return {
        "brand": "Chevrolet",
        "model": "Captiva",
        "year": 2020,
        "color": "white",
        "plate": "01A123BC",
        "mileage": 50000,
    }


# ---- Create ---------------------------------------------------------------
@pytest.mark.integration
def test_create_car_detects_plate_type_standard(api_client) -> None:
    token = _register(api_client)
    resp = api_client.post(CARS, json=_default_car(), headers=_hdr(token))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["plate"] == "01A123BC"
    assert body["plate_type"] == "standard"
    assert body["mileage"] == 50000


@pytest.mark.integration
def test_create_car_detects_plate_type_legal(api_client) -> None:
    token = _register(api_client)
    car = _default_car()
    car["plate"] = "01 123 ABC"
    resp = api_client.post(CARS, json=car, headers=_hdr(token))
    assert resp.status_code == 201
    assert resp.json()["plate_type"] == "legal"


@pytest.mark.integration
def test_create_car_rejects_garbage_plate(api_client) -> None:
    token = _register(api_client)
    car = _default_car()
    car["plate"] = "!!!"
    resp = api_client.post(CARS, json=car, headers=_hdr(token))
    assert resp.status_code == 422


@pytest.mark.integration
def test_create_car_duplicate_plate_returns_409(api_client) -> None:
    t1 = _register(api_client, "+998901111111")
    api_client.post(CARS, json=_default_car(), headers=_hdr(t1))

    # Even a *different* owner cannot reuse the plate.
    t2 = _register(api_client, "+998902222222")
    resp = api_client.post(CARS, json=_default_car(), headers=_hdr(t2))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CAR_PLATE_DUPLICATE"


@pytest.mark.integration
def test_create_car_rejects_too_old_year(api_client) -> None:
    token = _register(api_client)
    car = _default_car()
    car["year"] = 1900
    resp = api_client.post(CARS, json=car, headers=_hdr(token))
    assert resp.status_code == 422


# ---- List / Get / Update / Delete -----------------------------------------
@pytest.mark.integration
def test_list_only_own_cars(api_client) -> None:
    t1 = _register(api_client, "+998901111111")
    api_client.post(CARS, json=_default_car(), headers=_hdr(t1))

    t2 = _register(api_client, "+998902222222")
    mine = api_client.get(CARS, headers=_hdr(t2)).json()
    assert mine == []

    theirs = api_client.get(CARS, headers=_hdr(t1)).json()
    assert len(theirs) == 1


@pytest.mark.integration
def test_cannot_read_other_users_car(api_client) -> None:
    t1 = _register(api_client, "+998901111111")
    created = api_client.post(CARS, json=_default_car(), headers=_hdr(t1)).json()
    car_id = created["id"]

    t2 = _register(api_client, "+998902222222")
    resp = api_client.get(f"{CARS}/{car_id}", headers=_hdr(t2))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CAR_NOT_OWNER"


@pytest.mark.integration
def test_patch_and_delete_car(api_client) -> None:
    token = _register(api_client)
    created = api_client.post(CARS, json=_default_car(), headers=_hdr(token)).json()
    car_id = created["id"]

    patched = api_client.patch(
        f"{CARS}/{car_id}",
        json={"color": "black", "mileage": 55000},
        headers=_hdr(token),
    ).json()
    assert patched["color"] == "black"
    assert patched["mileage"] == 55000

    resp = api_client.delete(f"{CARS}/{car_id}", headers=_hdr(token))
    assert resp.status_code == 204
    assert api_client.get(CARS, headers=_hdr(token)).json() == []


# ---- Mileage rules --------------------------------------------------------
@pytest.mark.integration
def test_mileage_cannot_decrease(api_client) -> None:
    token = _register(api_client)
    created = api_client.post(CARS, json=_default_car(), headers=_hdr(token)).json()
    car_id = created["id"]
    resp = api_client.patch(
        f"{CARS}/{car_id}", json={"mileage": 10000}, headers=_hdr(token)
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "CAR_MILEAGE_DECREASE"


@pytest.mark.integration
def test_post_mileage_reading_updates_car(api_client) -> None:
    token = _register(api_client)
    created = api_client.post(CARS, json=_default_car(), headers=_hdr(token)).json()
    car_id = created["id"]

    resp = api_client.post(
        f"{CARS}/{car_id}/mileage", json={"value": 60000}, headers=_hdr(token)
    )
    assert resp.status_code == 200
    assert resp.json()["mileage"] == 60000


# ---- Recommendations ------------------------------------------------------
@pytest.mark.integration
def test_recommendations_due_at_milestones(api_client) -> None:
    token = _register(api_client)
    car = _default_car()
    car["mileage"] = 30000
    created = api_client.post(CARS, json=car, headers=_hdr(token)).json()
    car_id = created["id"]
    resp = api_client.get(
        f"{CARS}/{car_id}/recommendations", headers=_hdr(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mileage"] == 30000
    due = [i for i in body["items"] if i["priority"] == "due"]
    # At 30k: oil (10k), air/cabin (20k), fuel filter & brakes (30k) all due-ish.
    assert any(i["service_type"] == "oil_change" for i in due)
