"""Auth repository — the only place that touches ``users`` and ``refresh_tokens``.

Keeps SQL out of service code. Every function takes a ``Session`` as the first
argument; the caller is responsible for committing / rolling back (the request
dep ``get_db`` does this automatically).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.auth.models import RefreshToken
from app.modules.users.models import User

UUIDLike = Union[UUID, str]


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    return db.execute(select(User).where(User.phone == phone)).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: UUIDLike) -> Optional[User]:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def create_user(
    db: Session,
    *,
    phone: str,
    password_hash: str,
    full_name: Optional[str] = None,
    email: Optional[str] = None,
    city: Optional[str] = None,
    role: str = "customer",
) -> User:
    user = User(
        phone=phone,
        password_hash=password_hash,
        full_name=full_name,
        email=email,
        city=city,
        role=role,
    )
    db.add(user)
    db.flush()  # populate user.id without committing the outer txn
    return user


def update_password(db: Session, user_id: UUIDLike, *, password_hash: str) -> None:
    db.execute(
        update(User).where(User.id == user_id).values(password_hash=password_hash)
    )


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------
def save_refresh(
    db: Session,
    *,
    user_id: UUIDLike,
    token_hash: str,
    expires_at: datetime,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip=ip,
    )
    db.add(token)
    db.flush()
    return token


def get_active_refresh(db: Session, token_hash: str) -> Optional[RefreshToken]:
    """Return the token only if it is neither revoked nor expired."""
    now = datetime.now(timezone.utc)
    stmt = select(RefreshToken).where(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > now,
    )
    return db.execute(stmt).scalar_one_or_none()


def revoke_refresh(db: Session, token_hash: str) -> int:
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    return int(result.rowcount or 0)


def revoke_all_user_refresh(db: Session, user_id: UUIDLike) -> int:
    """Kill every active refresh token for ``user_id`` — used on password reset."""
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    return int(result.rowcount or 0)
