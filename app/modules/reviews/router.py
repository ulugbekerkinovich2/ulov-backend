"""Reviews endpoints — customer writes + read.

Public read of per-centre reviews lives under /service-centers/{id}/reviews
in Phase 3 (needs the centers table to validate the path).
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_customer, get_db
from app.modules.reviews import service as svc
from app.modules.reviews.schemas import ReviewCreateIn, ReviewOut

router = APIRouter()


@router.post(
    "",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a review",
)
def create_review(
    body: ReviewCreateIn,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> ReviewOut:
    review = svc.create(
        db,
        user_id=user.id,
        center_id=body.center_id,
        service_id=body.service_id,
        rating=body.rating,
        text=body.text,
    )
    return ReviewOut.from_orm(review)


@router.get("/me", response_model=List[ReviewOut], summary="My own reviews")
def list_my_reviews(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> List[ReviewOut]:
    return [
        ReviewOut.from_orm(r)
        for r in svc.list_mine(db, user.id, limit=limit, offset=offset)
    ]


@router.get(
    "/center/{center_id}",
    response_model=List[ReviewOut],
    summary="Reviews for a centre (public)",
)
def list_center_reviews(
    center_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[ReviewOut]:
    return [
        ReviewOut.from_orm(r)
        for r in svc.list_for_center(db, center_id, limit=limit, offset=offset)
    ]
