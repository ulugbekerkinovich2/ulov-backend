"""Users domain logic — thin today, grows with self-service features."""

from __future__ import annotations

from typing import Optional, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.users import repository as repo
from app.modules.users.models import User

UUIDLike = Union[UUID, str]


def get_me(db: Session, user_id: UUIDLike) -> User:
    user = repo.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    return user


def patch_me(
    db: Session,
    user_id: UUIDLike,
    *,
    full_name: Optional[str] = None,
    email: Optional[str] = None,
    city: Optional[str] = None,
) -> User:
    updated = repo.update_fields(
        db, user_id, full_name=full_name, email=email, city=city
    )
    if updated is None:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    return updated


def set_avatar(
    db: Session, user_id: UUIDLike, *, avatar_url: Optional[str]
) -> User:
    # ``None`` is a valid value — it clears the avatar. Use a sentinel-free
    # update that always writes the field regardless of None-ness.
    user = repo.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    user.avatar_url = avatar_url
    db.flush()
    return user
