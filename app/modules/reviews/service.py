"""Reviews domain logic."""

from __future__ import annotations

from typing import List, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.reviews import repository as repo
from app.modules.reviews.models import Review

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


def create(
    db: Session,
    *,
    user_id: UUIDLike,
    center_id: UUIDLike,
    service_id: UUIDLike = None,
    rating: int,
    text: str = None,
) -> Review:
    review = repo.create(
        db,
        user_id=user_id,
        center_id=center_id,
        service_id=service_id,
        rating=rating,
        text=text,
    )
    log.info(
        "review_created",
        review_id=str(review.id),
        center_id=str(center_id),
        rating=rating,
    )
    return review


def list_mine(db: Session, user_id: UUIDLike, *, limit: int = 50, offset: int = 0) -> List[Review]:
    return repo.list_by_user(db, user_id, limit=limit, offset=offset)


def list_for_center(
    db: Session, center_id: UUIDLike, *, limit: int = 50, offset: int = 0
) -> List[Review]:
    return repo.list_by_center(db, center_id, limit=limit, offset=offset)
