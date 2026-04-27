"""Service centres — owned by one `owner` user; host many `mechanics` + `services`."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from app.db.base import Base, TimestampMixin, UUIDMixin


class ServiceCenter(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "service_centers"

    owner_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    address = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # (lon, lat) tuples, stored as JSONB for local compat (formerly Geography)
    location = Column(JSONB, nullable=True)

    # schedule = {"mon": {"open": "09:00", "close": "19:00"}, ...}
    schedule = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # Free-form list of service types this centre offers.
    services = Column(ARRAY(String(64)), nullable=False, server_default=text("'{}'::text[]"))

    avatar_url = Column(String(500), nullable=True)

    # Billing — populated by Phase 6. Left nullable for now.
    subscription_plan_id = Column(UUID(as_uuid=True), nullable=True)
    subscription_until = Column(String(32), nullable=True)  # ISO ts; tightened P6
