"""Static-credentials AuthenticationBackend for the sqladmin panel.

Intentionally simple: a single ``ADMIN_USERNAME`` / ``ADMIN_PASSWORD`` pair
stored in env vars. The admin UI is not for end users — it's for the small
ops/DBA team — so we don't try to integrate it with the JWT customer/staff
auth used by the public API.

Sessions live in a signed cookie (Starlette's SessionMiddleware, set up by
sqladmin itself). Rotate ``ADMIN_SESSION_SECRET`` to log everyone out.
"""

from __future__ import annotations

import hmac

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.config import settings


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = (form.get("username") or "").strip()
        password = form.get("password") or ""

        # Constant-time comparison so the response time doesn't leak whether
        # the username happened to match.
        ok = (
            bool(settings.ADMIN_USERNAME)
            and bool(settings.ADMIN_PASSWORD)
            and hmac.compare_digest(username, settings.ADMIN_USERNAME)
            and hmac.compare_digest(password, settings.ADMIN_PASSWORD)
        )
        if not ok:
            return False
        request.session.update({"sqladmin_user": username})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("sqladmin_user"))
