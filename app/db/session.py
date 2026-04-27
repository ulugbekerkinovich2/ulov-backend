"""SQLAlchemy engine + session factory.

Keep this file free of business logic. The FastAPI request-scoped session is
produced by ``app.deps.get_db``.
"""

from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _build_engine() -> Engine:
    return create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_POOL_MAX_OVERFLOW,
        pool_pre_ping=True,  # reconnect dead connections transparently
        echo=settings.DATABASE_ECHO,
        future=True,
    )


engine: Engine = _build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_engine() -> Engine:
    """Return the module-level engine (tests may replace it)."""
    return engine


def session_scope() -> Iterator[Session]:
    """Context manager for code running outside a request (scripts, workers).

    Not used inside request handlers — those use ``app.deps.get_db``.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
