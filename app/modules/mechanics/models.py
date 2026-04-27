"""Mechanics — staff roster of a service centre.

Each mechanic logs in with a centre-scoped ``login`` (not a phone like
customers do). The owner manages the roster. Soft-delete preserves history
for past services authored by the mechanic.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from app.db.base import Base, UUIDMixin


class Mechanic(UUIDMixin, Base):
    __tablename__ = "mechanics"

    center_id = Column(
        UUID(as_uuid=True),
        ForeignKey("service_centers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    full_name = Column(String(255), nullable=False)
    login = Column(String(64), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)

    service_types = Column(
        ARRAY(String(64)), nullable=False, server_default=text("'{}'::text[]")
    )

    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
