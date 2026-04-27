"""Reviews — customers rate service centres (and optionally a specific service).

``center_id`` and ``service_id`` are kept as plain UUID columns (no FK) until
Phase 3 introduces the centres / services tables. Phase 3 migration adds the
FK constraints retroactively; no app-code change needed.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin, UUIDMixin


class Review(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # FK to centers in Phase 3 — for now a plain UUID so the table stands alone.
    center_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    service_id = Column(UUID(as_uuid=True), nullable=True)

    rating = Column(SmallInteger, nullable=False)
    text = Column(Text, nullable=True)

    reply = Column(Text, nullable=True)
    reply_at = Column(String(32), nullable=True)  # ISO ts; tightened later
