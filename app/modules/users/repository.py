"""Users repository — the single home for SQL against the ``users`` table.

``auth`` module has its own repository with some of the same helpers; keep
them in sync. Writes outside of registration go through this module.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.users.models import User

UUIDLike = Union[UUID, str]


def get_by_id(db: Session, user_id: UUIDLike) -> Optional[User]:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def update_fields(db: Session, user_id: UUIDLike, **fields: Any) -> Optional[User]:
    """Update any non-``None`` values in ``fields`` and return the refreshed row.

    Returns ``None`` if the user does not exist.
    """
    values: Dict[str, Any] = {k: v for k, v in fields.items() if v is not None}
    if not values:
        return get_by_id(db, user_id)
    db.execute(update(User).where(User.id == user_id).values(**values))
    db.flush()
    # See cars.repository.update_fields — populate_existing forces the ORM
    # to refresh the identity-mapped row instead of handing back the
    # pre-update cached attributes.
    stmt = (
        select(User)
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
    )
    return db.execute(stmt).scalar_one_or_none()
