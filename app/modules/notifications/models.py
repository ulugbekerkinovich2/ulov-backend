"""Notifications inbox + device tokens.

Phase 2 covers only the in-app channel (DB rows + /read endpoint). Phase 7
adds the dispatcher that decides push/SMS based on user preferences.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base, TimestampMixin, UUIDMixin

DEVICE_PLATFORM_VALUES = ("ios", "android", "web")

device_platform_enum = PG_ENUM(
    *DEVICE_PLATFORM_VALUES,
    name="device_platform",
    create_type=True,
)


class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind = Column(String(64), nullable=False, index=True)  # e.g. "service.completed"
    title = Column(String(255), nullable=False)
    body = Column(String(2000), nullable=True)
    payload = Column(JSONB, nullable=False, server_default="{}")
    read_at = Column(DateTime(timezone=True), nullable=True, index=True)


class Device(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("user_id", "token", name="uq_devices_user_token"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # FCM / APNs / web-push endpoint identifier.
    token = Column(String(500), nullable=False)
    platform = Column(device_platform_enum, nullable=False)
