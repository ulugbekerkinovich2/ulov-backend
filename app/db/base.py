"""Declarative base and common mixins.

Every ORM model imports ``Base`` from here and (usually) mixes in
:class:`UUIDMixin` + :class:`TimestampMixin`.

SQLAlchemy 1.4 is used in ``future=True`` mode so the migration to 2.0 (when
we drop Python 3.8) is a no-op for repository code.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, declared_attr

Base = declarative_base()


class UUIDMixin:
    """Primary key column — server-generated UUID v4."""

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class TimestampMixin:
    """Opinionated created/updated columns in UTC."""

    @declared_attr
    def created_at(cls) -> Column:  # noqa: N805
        return Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )

    @declared_attr
    def updated_at(cls) -> Column:  # noqa: N805
        return Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )


def utcnow() -> datetime:
    """Helper so app code never calls ``datetime.utcnow()`` (naive)."""
    from datetime import timezone

    return datetime.now(tz=timezone.utc)
