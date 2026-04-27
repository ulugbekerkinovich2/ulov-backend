"""Smoke tests — the app imports, boots, and the meta endpoints respond.

These are the only tests that run in CI before any real module exists.
"""

from __future__ import annotations


def test_root_endpoint(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "ulov-backend"
    assert body["docs"] == "/docs"


def test_health_live(client) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_v1_ping(client) -> None:
    response = client.get("/api/v1/ping")
    assert response.status_code == 200
    assert response.json() == {"pong": True}


def test_openapi_generated(client) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "ULOV+ API"


def test_request_id_echoed(client) -> None:
    # The middleware should echo the supplied request-id (and emit one if missing).
    rid = "fixed-req-id-for-assert"
    response = client.get("/health/live", headers={"X-Request-ID": rid})
    assert response.headers.get("X-Request-ID") == rid


def test_unknown_route_returns_json_error(client) -> None:
    response = client.get("/this-does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["code"].startswith("HTTP_")
