"""Firebase Cloud Messaging (HTTP v1) push client.

Loads the service-account JSON once, mints a short-lived OAuth2 token via
``google-auth``, and POSTs a single message at a time. Token caching is in
process memory; failures don't propagate — a push is best-effort.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from app.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class FcmClient:
    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    @staticmethod
    def is_configured() -> bool:
        return bool(
            settings.FCM_PROJECT_ID
            and settings.FCM_SERVICE_ACCOUNT_JSON
            and os.path.exists(settings.FCM_SERVICE_ACCOUNT_JSON)
        )

    def _load_credentials(self):
        # Imported lazily so the dep is optional in dev.
        from google.oauth2 import service_account  # type: ignore

        return service_account.Credentials.from_service_account_file(
            settings.FCM_SERVICE_ACCOUNT_JSON, scopes=[FCM_SCOPE]
        )

    def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token
        from google.auth.transport.requests import Request as _Request  # type: ignore

        creds = self._load_credentials()
        creds.refresh(_Request())
        self._token = creds.token
        # Refresh 5 min before the upstream expiry.
        self._token_expires_at = (creds.expiry.timestamp() - 300) if creds.expiry else (time.time() + 1800)
        return self._token

    async def send(
        self,
        *,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        if not self.is_configured():
            log.info(
                "fcm_dev_short_circuit", device_token=device_token[:12], title=title
            )
            return True, None

        access_token = self._ensure_token()
        message: Dict[str, Any] = {
            "message": {
                "token": device_token,
                "notification": {"title": title, "body": body},
            }
        }
        if data:
            message["message"]["data"] = {k: str(v) for k, v in data.items()}

        url = (
            f"https://fcm.googleapis.com/v1/projects/"
            f"{settings.FCM_PROJECT_ID}/messages:send"
        )
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                url,
                content=json.dumps(message),
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
        if resp.status_code >= 400:
            log.warning(
                "fcm_send_failed", status=resp.status_code, body=resp.text[:200]
            )
            return False, None
        name = resp.json().get("name")
        log.info("fcm_sent", device_token=device_token[:12], name=name)
        return True, name


client = FcmClient()
