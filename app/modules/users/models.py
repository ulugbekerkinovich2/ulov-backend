"""User ORM model.

The ``User`` row is the platform's single authentication principal. The
``role`` column governs which of the two frontends (and which subsections)
the user is allowed to touch.

  * ``customer`` — front-user
  * ``mechanic`` — front-admin, scoped to a ``center_id``
  * ``owner``    — front-admin, manages their centre
  * ``admin``    — platform staff (no dedicated UI yet)
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin, UUIDMixin

# Declared with ``create_type=False`` — the enum type is owned by the Alembic
# migration; ``create_all`` (used only in tests) will still emit the type
# because the first migration creates it before ``Base.metadata.create_all``
# is called. For pure create_all usage (tests), flip to True.
USER_ROLE_VALUES = ("customer", "mechanic", "owner", "admin")

user_role_type = PG_ENUM(
    *USER_ROLE_VALUES,
    name="user_role",
    create_type=True,  # tests rely on create_all; migration uses checkfirst
)


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # E.164 format: +998XXXXXXXXX (up to ~15 digits globally).
    phone = Column(String(20), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)

    full_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    city = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)

    role = Column(user_role_type, nullable=False, server_default="customer")
    # For mechanic / owner — the centre they belong to. Nullable for
    # customer / admin. Actual FK constraint is added in Phase 3 when the
    # centers table exists; a plain UUID column is enough for now.
    center_id = Column(UUID(as_uuid=True), nullable=True)

    is_active = Column(Boolean, nullable=False, server_default="true")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} phone={self.phone} role={self.role}>"
