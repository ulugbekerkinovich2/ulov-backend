"""Eskiz client — dev short-circuit + login retry behaviour."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_dev_short_circuit_when_unconfigured(monkeypatch):
    """Without credentials configured, send_sms must succeed without making
    any network call — keeps dev / CI green."""
    monkeypatch.setattr("app.config.settings.ESKIZ_EMAIL", "")
    monkeypatch.setattr("app.config.settings.ESKIZ_PASSWORD", "")
    from app.integrations.eskiz import EskizClient

    ok, ref = await EskizClient().send_sms(phone="+998901234567", message="hi")
    assert ok is True
    assert ref is None


@pytest.mark.asyncio
async def test_send_uses_token_then_retries_on_401(monkeypatch):
    """If Eskiz returns 401, the client must re-login once and retry."""
    monkeypatch.setattr("app.config.settings.ESKIZ_EMAIL", "x@y.z")
    monkeypatch.setattr("app.config.settings.ESKIZ_PASSWORD", "secret")

    calls = {"login": 0, "send": 0}

    class _StubResp:
        def __init__(self, status_code=200, payload=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = ""

        def json(self):
            return self._payload

    class _StubAsyncClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, **_):
            if "/auth/login" in url:
                calls["login"] += 1
                return _StubResp(200, {"data": {"token": f"tok-{calls['login']}"}})
            calls["send"] += 1
            if calls["send"] == 1:
                return _StubResp(401, {})
            return _StubResp(200, {"id": 12345, "status": "waiting"})

    monkeypatch.setattr("app.integrations.eskiz.httpx.AsyncClient", _StubAsyncClient)
    from app.integrations.eskiz import EskizClient

    ok, ref = await EskizClient().send_sms(phone="+998901234567", message="hi")
    assert ok is True
    assert ref == "12345"
    assert calls["login"] == 2  # initial login + refresh-on-401
    assert calls["send"] == 2
