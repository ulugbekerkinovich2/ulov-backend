"""WebSocket smoke tests.

We exercise the auth + handshake paths. End-to-end pub-sub fan-out requires
a real Redis with broadcast semantics; ``fakeredis`` does support pub/sub
but routing test events through a TestClient WebSocket is timing-sensitive,
so the test below focuses on the behaviour we can verify deterministically:

* unauthenticated connections close with code 4401
* authenticated, authorised connections receive the ``ws.ready`` greeting
* customers cannot subscribe to other customers' service WS
"""

from __future__ import annotations

import pytest
from starlette.websockets import WebSocketDisconnect

from tests.modules.conftest import _create_car, _create_center, _hdr, _register


def _intake(api_client, owner_token, center_id, plate):
    return api_client.post(
        f"/api/v1/service-centers/{center_id}/intakes",
        json={"plate": plate, "mileage_at_intake": 40000},
        headers=_hdr(owner_token),
    ).json()


@pytest.mark.integration
def test_ws_service_rejects_missing_token(api_client) -> None:
    with pytest.raises(WebSocketDisconnect) as ex:
        with api_client.websocket_connect("/api/v1/ws/services/00000000-0000-0000-0000-000000000000"):
            pass
    assert ex.value.code == 4401


@pytest.mark.integration
def test_ws_service_rejects_other_customer(api_client, owner_token, customer_token) -> None:
    center = _create_center(api_client, owner_token)
    _create_car(api_client, customer_token, plate="01W001AA")
    intake = _intake(api_client, owner_token, center["id"], "01W001AA")

    other_token = _register(api_client, "+998904000001")
    with pytest.raises(WebSocketDisconnect) as ex:
        with api_client.websocket_connect(
            f"/api/v1/ws/services/{intake['id']}?access_token={other_token}"
        ):
            pass
    assert ex.value.code == 4403


@pytest.mark.integration
def test_ws_service_owner_handshake_ok(api_client, owner_token, customer_token) -> None:
    center = _create_center(api_client, owner_token)
    _create_car(api_client, customer_token, plate="01W002BB")
    intake = _intake(api_client, owner_token, center["id"], "01W002BB")

    with api_client.websocket_connect(
        f"/api/v1/ws/services/{intake['id']}?access_token={owner_token}"
    ) as ws:
        msg = ws.receive_json()
        assert msg["type"] == "ws.ready"
        assert msg["channels"] == [f"events:service:{intake['id']}"]


@pytest.mark.integration
def test_ws_center_owner_handshake_ok(api_client, owner_token) -> None:
    center = _create_center(api_client, owner_token)

    with api_client.websocket_connect(
        f"/api/v1/ws/centers/{center['id']}?access_token={owner_token}"
    ) as ws:
        msg = ws.receive_json()
        assert msg["type"] == "ws.ready"
        assert msg["channels"] == [f"events:services:{center['id']}"]


@pytest.mark.integration
def test_ws_center_rejects_outside_owner(api_client, owner_token, db) -> None:
    center = _create_center(api_client, owner_token)
    from tests.modules.conftest import _make_user_with_role, _token

    other = _make_user_with_role(db, phone="+998919199991", role="owner")
    db.flush()
    other_token = _token(other.id, "owner")

    with pytest.raises(WebSocketDisconnect) as ex:
        with api_client.websocket_connect(
            f"/api/v1/ws/centers/{center['id']}?access_token={other_token}"
        ):
            pass
    assert ex.value.code == 4403
