"""Eskiz SMS gateway client.

Eskiz issues a JWT after authenticating with email/password; we cache it in
process memory and refresh on 401. Sends are POST to ``/api/message/sms/send``
with the JWT in ``Authorization: Bearer ...``.

In dev (no credentials configured) we short-circuit to a no-op that logs the
SMS body — keeps the OTP flow functional without external dependencies.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

import httpx

from app.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

ESKIZ_BASE = "https://notify.eskiz.uz/api"


class EskizError(Exception):
    """Wraps any non-2xx response from Eskiz so callers can decide retry."""


class EskizClient:
    """Async Eskiz client with token cache + automatic refresh on 401."""

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.ESKIZ_EMAIL and settings.ESKIZ_PASSWORD)

    # ---- Auth -----------------------------------------------------------
    async def _login(self, http: httpx.AsyncClient) -> str:
        resp = await http.post(
            f"{ESKIZ_BASE}/auth/login",
            data={
                "email": settings.ESKIZ_EMAIL,
                "password": settings.ESKIZ_PASSWORD,
            },
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise EskizError(f"login failed: {resp.status_code} {resp.text}")
        token = (resp.json().get("data") or {}).get("token")
        if not token:
            raise EskizError("login response missing token")
        # Eskiz tokens last 30 days; refresh proactively after 25.
        self._token = token
        self._token_expires_at = time.time() + 25 * 24 * 3600
        return token

    async def _ensure_token(self, http: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token
        return await self._login(http)

    # ---- Send -----------------------------------------------------------
    async def send_sms(
        self, *, phone: str, message: str
    ) -> Tuple[bool, Optional[str]]:
        """Return ``(ok, provider_id)``.

        ``phone`` must be a digits-only Uzbek number (e.g. ``998901234567`` —
        Eskiz rejects the leading ``+`` form).
        """
        if not self.is_configured():
            log.info("sms_dev_short_circuit", phone=phone, message=message)
            return True, None

        async with httpx.AsyncClient() as http:
            token = await self._ensure_token(http)
            payload = {
                "mobile_phone": phone.lstrip("+"),
                "message": message,
                "from": settings.ESKIZ_FROM,
            }
            resp = await http.post(
                f"{ESKIZ_BASE}/message/sms/send",
                data=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15.0,
            )
            if resp.status_code == 401:
                # Stale token — re-login once and retry.
                self._token = None
                token = await self._ensure_token(http)
                resp = await http.post(
                    f"{ESKIZ_BASE}/message/sms/send",
                    data=payload,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15.0,
                )
            if resp.status_code >= 400:
                log.warning(
                    "sms_send_failed",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
                raise EskizError(f"send failed: {resp.status_code}")

            body = resp.json()
            log.info(
                "sms_sent",
                phone=phone,
                provider_id=body.get("id"),
                status=body.get("status"),
            )
            provider_id = body.get("id")
            return True, str(provider_id) if provider_id is not None else None


# Module-level singleton — safe because state is just the cached token.
client = EskizClient()
