"""Audit log — record on transition + admin-only browse."""

from __future__ import annotations

import pytest

from tests.modules.conftest import _create_car, _create_center, _hdr


def _intake(api_client, owner_token, center_id, plate):
    return api_client.post(
        f"/api/v1/service-centers/{center_id}/intakes",
        json={"plate": plate, "mileage_at_intake": 40000},
        headers=_hdr(owner_token),
    ).json()


@pytest.mark.integration
def test_transition_writes_audit_row(
    api_client, owner_token, customer_token, admin_token
) -> None:
    center = _create_center(api_client, owner_token)
    _create_car(api_client, customer_token, plate="01Z111AA")
    s = _intake(api_client, owner_token, center["id"], "01Z111AA")
    api_client.post(
        f"/api/v1/services/{s['id']}/transition",
        json={"to_status": "in_progress"},
        headers=_hdr(owner_token),
    )

    r = api_client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "service", "entity_id": s["id"]},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) >= 1
    assert any(
        row["action"] == "service.transitioned"
        and row["after"] == {"status": "in_progress"}
        for row in rows
    )


@pytest.mark.integration
def test_audit_logs_admin_only(api_client, owner_token) -> None:
    r = api_client.get("/api/v1/audit-logs", headers=_hdr(owner_token))
    assert r.status_code == 403
