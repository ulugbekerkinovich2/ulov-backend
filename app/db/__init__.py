"""Database session + declarative base.

Single engine, single SessionLocal. Modules import :class:`Base` from
``app.db.base`` and use :func:`app.deps.get_db` at request time.
"""

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.session import SessionLocal, engine, get_engine

__all__ = ["Base", "TimestampMixin", "UUIDMixin", "SessionLocal", "engine", "get_engine"]
