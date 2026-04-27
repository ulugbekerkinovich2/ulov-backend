"""Notifications endpoints — inbox + device registration."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_user, get_db
from app.modules.notifications import service as svc
from app.modules.notifications.schemas import (
    DeviceIn,
    DeviceOut,
    NotificationOut,
)

router = APIRouter()


@router.get("", summary="My notifications inbox")
def list_notifications(
    unread: bool = Query(False, description="Return only unread notifications"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    items, unread_count = svc.list_inbox(
        db, user.id, unread_only=unread, limit=limit, offset=offset
    )
    return {
        "unread_count": unread_count,
        "items": [NotificationOut.from_orm(n) for n in items],
    }


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark a notification as read",
    response_model=None,
)
def mark_notification_read(
    notification_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc.mark_read(db, notification_id, user.id)


# ---- Devices -------------------------------------------------------------
devices_router = APIRouter()


@devices_router.post(
    "",
    response_model=DeviceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a push token for this device",
)
def register_device(
    body: DeviceIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceOut:
    device = svc.register_device(
        db, user_id=user.id, token=body.token, platform=body.platform
    )
    return DeviceOut.from_orm(device)
