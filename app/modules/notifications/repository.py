"""Notifications + devices repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.notifications.models import Device, Notification

UUIDLike = Union[UUID, str]


# ---- Notifications ---------------------------------------------------------
def create(db: Session, **fields: Any) -> Notification:
    n = Notification(**fields)
    db.add(n)
    db.flush()
    return n


def list_for_user(
    db: Session,
    user_id: UUIDLike,
    *,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Notification], int]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    items = list(db.execute(stmt).scalars())

    unread_stmt = (
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    unread_count = int(db.execute(unread_stmt).scalar_one() or 0)
    return items, unread_count


def get_for_user(
    db: Session, notification_id: UUIDLike, user_id: UUIDLike
) -> Optional[Notification]:
    stmt = select(Notification).where(
        Notification.id == notification_id, Notification.user_id == user_id
    )
    return db.execute(stmt).scalar_one_or_none()


def mark_read(
    db: Session, notification_id: UUIDLike, user_id: UUIDLike
) -> int:
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    return int(result.rowcount or 0)


# ---- Devices ---------------------------------------------------------------
def upsert_device(
    db: Session, *, user_id: UUIDLike, token: str, platform: str
) -> Device:
    stmt = select(Device).where(
        Device.user_id == user_id, Device.token == token
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        existing.platform = platform
        db.flush()
        return existing
    device = Device(user_id=user_id, token=token, platform=platform)
    db.add(device)
    db.flush()
    return device


def list_devices_for_user(db: Session, user_id: UUIDLike):
    return list(
        db.execute(select(Device).where(Device.user_id == user_id)).scalars()
    )
