"""Notifications domain logic.

Phase 2 scope:
  * In-app inbox (DB rows).
  * Device token registration (used later by the push dispatcher).

Phase 7 extends this with an event-driven dispatcher that fans out to
FCM/APNs/SMS based on user preferences.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.modules.notifications import repository as repo
from app.modules.notifications.models import Device, Notification

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


def create_notification(
    db: Session,
    *,
    user_id: UUIDLike,
    kind: str,
    title: str,
    body: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Notification:
    """Public entry-point for any module that needs to notify a user.

    Persists the inbox row, then fires a best-effort FCM push to every
    device this user has registered. Push failures are logged but do not
    propagate — the in-app inbox is always the source of truth.
    """
    n = repo.create(
        db,
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        payload=payload or {},
    )
    log.info("notification_created", user_id=str(user_id), kind=kind, id=str(n.id))
    _dispatch_push(db, user_id, title=title, body=body or "", payload=payload or {})
    return n


def _dispatch_push(
    db: Session,
    user_id: UUIDLike,
    *,
    title: str,
    body: str,
    payload: Dict[str, Any],
) -> None:
    # Done inside a try/except so an FCM outage never breaks the caller's
    # transaction or the test suite (the dev short-circuit is hit when no
    # credentials are configured).
    try:
        import asyncio

        from app.integrations.fcm import client as fcm

        devices = repo.list_devices_for_user(db, user_id)
        if not devices:
            return

        async def _send_all() -> None:
            for d in devices:
                try:
                    await fcm.send(
                        device_token=d.token,
                        title=title,
                        body=body,
                        data={k: str(v) for k, v in payload.items()},
                    )
                except Exception:  # noqa: BLE001
                    log.exception("push_send_failed", device_id=str(d.id))

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_send_all())
        except RuntimeError:
            asyncio.run(_send_all())
    except Exception:  # noqa: BLE001
        log.exception("push_dispatch_failed", user_id=str(user_id))


def list_inbox(
    db: Session,
    user_id: UUIDLike,
    *,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Notification], int]:
    return repo.list_for_user(
        db, user_id, unread_only=unread_only, limit=limit, offset=offset
    )


def mark_read(
    db: Session, notification_id: UUIDLike, user_id: UUIDLike
) -> None:
    affected = repo.mark_read(db, notification_id, user_id)
    if affected == 0:
        # Either the notification doesn't exist, is not ours, or was already read.
        # Distinguish: was it ours at all?
        existing = repo.get_for_user(db, notification_id, user_id)
        if existing is None:
            raise NotFoundError(
                "Notification not found", code="NOTIFICATION_NOT_FOUND"
            )
        # Otherwise: already read — idempotent, not an error.


def register_device(
    db: Session,
    *,
    user_id: UUIDLike,
    token: str,
    platform: str,
) -> Device:
    device = repo.upsert_device(
        db, user_id=user_id, token=token, platform=platform
    )
    log.info("device_registered", user_id=str(user_id), platform=platform)
    return device
