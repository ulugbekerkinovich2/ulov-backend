"""Reviews repository."""

from __future__ import annotations

from typing import List, Optional, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.reviews.models import Review

UUIDLike = Union[UUID, str]


def create(db: Session, **fields: object) -> Review:
    review = Review(**fields)
    db.add(review)
    db.flush()
    return review


def list_by_user(db: Session, user_id: UUIDLike, *, limit: int = 50, offset: int = 0) -> List[Review]:
    stmt = (
        select(Review)
        .where(Review.user_id == user_id)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars())


def list_by_center(db: Session, center_id: UUIDLike, *, limit: int = 50, offset: int = 0) -> List[Review]:
    stmt = (
        select(Review)
        .where(Review.center_id == center_id)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars())


def get_by_id(db: Session, review_id: UUIDLike) -> Optional[Review]:
    return db.execute(select(Review).where(Review.id == review_id)).scalar_one_or_none()
