"""SOS providers + request log."""

from __future__ import annotations

import pytest

from app.modules.sos.models import SosProvider
from tests.modules.conftest import _hdr


@pytest.mark.integration
def test_list_providers_filtered_by_category(api_client, db, customer_token) -> None:
    db.add_all([
        SosProvider(category="tow", name="A", phone="+1", city="Tashkent"),
        SosProvider(category="ambulance", name="B", phone="+2", city="Tashkent"),
    ])
    db.flush()

    r = api_client.get(
        "/api/v1/sos/providers",
        params={"category": "tow"},
        headers=_hdr(customer_token),
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["category"] == "tow"


@pytest.mark.integration
def test_create_request_logs_audit(api_client, customer_token) -> None:
    r = api_client.post(
        "/api/v1/sos/requests",
        json={"category": "tow", "lat": 41.31, "lng": 69.27, "note": "broken down"},
        headers=_hdr(customer_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "requested"
    assert body["lat"] == 41.31


@pytest.mark.integration
def test_create_request_requires_category_or_provider(
    api_client, customer_token
) -> None:
    r = api_client.post(
        "/api/v1/sos/requests",
        json={"note": "help"},
        headers=_hdr(customer_token),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SOS_PROVIDER_OR_CATEGORY_REQUIRED"
