"""Mechanics repository."""

from __future__ import annotations

from typing import Any, List, Optional, Union
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.modules.mechanics.models import Mechanic

UUIDLike = Union[UUID, str]


def create(db: Session, **fields: Any) -> Mechanic:
    m = Mechanic(**fields)
    db.add(m)
    db.flush()
    return m


def get_by_id(
    db: Session, mechanic_id: UUIDLike, *, include_deleted: bool = False
) -> Optional[Mechanic]:
    stmt = select(Mechanic).where(Mechanic.id == mechanic_id)
    if not include_deleted:
        stmt = stmt.where(Mechanic.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def get_by_login(db: Session, login: str) -> Optional[Mechanic]:
    stmt = (
        select(Mechanic)
        .where(Mechanic.login == login)
        .where(Mechanic.deleted_at.is_(None))
    )
    return db.execute(stmt).scalar_one_or_none()


def list_by_center(
    db: Session, center_id: UUIDLike, *, include_deleted: bool = False
) -> List[Mechanic]:
    stmt = select(Mechanic).where(Mechanic.center_id == center_id)
    if not include_deleted:
        stmt = stmt.where(Mechanic.deleted_at.is_(None))
    stmt = stmt.order_by(Mechanic.created_at)
    return list(db.execute(stmt).scalars())


def update_fields(db: Session, mechanic_id: UUIDLike, **fields: Any) -> Optional[Mechanic]:
    clean = {k: v for k, v in fields.items() if v is not None}
    if clean:
        db.execute(update(Mechanic).where(Mechanic.id == mechanic_id).values(**clean))
        db.flush()
    return get_by_id(db, mechanic_id, include_deleted=True)


def soft_delete(db: Session, mechanic_id: UUIDLike) -> int:
    result = db.execute(
        update(Mechanic)
        .where(Mechanic.id == mechanic_id)
        .where(Mechanic.deleted_at.is_(None))
        .values(deleted_at=utcnow())
    )
    return int(result.rowcount or 0)
