"""Mount the sqladmin panel at /admin (when configured).

Call :func:`mount_admin` from ``create_app`` after the routers have been
registered. The panel only appears when all three admin env vars are set —
otherwise the function logs a one-line skip message and returns.
"""

from __future__ import annotations

from sqladmin import Admin
from fastapi import FastAPI

from app.admin.auth import AdminAuth
from app.admin.views import ADMIN_VIEWS
from app.config import settings
from app.core.logging import get_logger
from app.db.session import engine

log = get_logger(__name__)


def mount_admin(app: FastAPI) -> None:
    """Attach the sqladmin sub-application to ``app`` at ``/admin``.

    Safe to call unconditionally — disables itself when any of the required
    env vars are missing so dev / CI doesn't expose an unauthenticated
    panel.
    """
    if not (
        settings.ADMIN_USERNAME
        and settings.ADMIN_PASSWORD
        and settings.ADMIN_SESSION_SECRET
    ):
        log.info("admin_panel_disabled", reason="missing ADMIN_* env vars")
        return

    admin = Admin(
        app=app,
        engine=engine,
        title="ULOV+ admin",
        base_url="/admin",
        authentication_backend=AdminAuth(secret_key=settings.ADMIN_SESSION_SECRET),
    )
    for view in ADMIN_VIEWS:
        admin.add_view(view)
    log.info("admin_panel_mounted", path="/admin", views=len(ADMIN_VIEWS))
