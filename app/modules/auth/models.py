"""Auth-owned tables.

We store **only a SHA-256 hash** of each refresh token — never the raw value.
A leak of this table does not let an attacker forge a working refresh cookie.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, UUIDMixin


class RefreshToken(UUIDMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True)

    # Audit metadata — useful for "log out everywhere" UIs later.
    user_agent = Column(String(500), nullable=True)
    ip = Column(String(45), nullable=True)  # ipv6-capable length

    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RefreshToken id={self.id} user_id={self.user_id}>"
