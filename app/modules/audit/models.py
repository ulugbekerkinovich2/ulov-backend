"""Audit log — append-only record of mutations.

One row per state-changing action. Stored as a JSONB ``before/after`` pair
so the UI can render diffs. The ``actor_user_id`` is the JWT subject; for
mechanic logins (no users row) it's left null but ``actor_role`` is still
recorded so we can attribute actions to "mechanic@center-X" later.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base, UUIDMixin


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"

    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_role = Column(String(32), nullable=True)

    action = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    before = Column(JSONB, nullable=True)
    after = Column(JSONB, nullable=True)
    meta = Column(JSONB, nullable=True)

    at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
