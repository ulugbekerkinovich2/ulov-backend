"""Notifications + devices DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: UUID
    user_id: UUID
    kind: str
    title: str
    body: Optional[str]
    payload: Dict[str, Any]
    read_at: Optional[datetime]
    created_at: datetime

    class Config:
        orm_mode = True


class NotificationsPage(BaseModel):
    unread_count: int
    items: list  # list of NotificationOut — kept loose to avoid circular import


class DeviceIn(BaseModel):
    token: str = Field(..., min_length=10, max_length=500)
    platform: str = Field(..., regex="^(ios|android|web)$")


class DeviceOut(BaseModel):
    id: UUID
    user_id: UUID
    token: str
    platform: str
    created_at: datetime

    class Config:
        orm_mode = True
