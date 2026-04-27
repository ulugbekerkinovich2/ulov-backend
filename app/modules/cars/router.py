"""Cars endpoints — CRUD + mileage + recommendations."""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_customer, get_db
from app.modules.cars import service as svc
from app.modules.cars.schemas import (
    CarCreateIn,
    CarOut,
    CarPatchIn,
    MileageReadingIn,
    RecommendationsOut,
)

router = APIRouter()


@router.get("", response_model=List[CarOut], summary="List my cars")
def list_my_cars(
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> List[CarOut]:
    return [CarOut.from_orm(c) for c in svc.list_mine(db, user.id)]


@router.post(
    "",
    response_model=CarOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new car to my garage",
)
def create_car(
    body: CarCreateIn,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CarOut:
    car = svc.create(db, user.id, body.dict(exclude_unset=False))
    return CarOut.from_orm(car)


@router.get("/{car_id}", response_model=CarOut, summary="Get one of my cars")
def get_car(
    car_id: UUID,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CarOut:
    return CarOut.from_orm(svc.get_owned(db, car_id, user.id))


@router.patch("/{car_id}", response_model=CarOut, summary="Update car fields")
def patch_car(
    car_id: UUID,
    body: CarPatchIn,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CarOut:
    car = svc.patch(db, car_id, user.id, body.dict(exclude_unset=True))
    return CarOut.from_orm(car)


@router.delete(
    "/{car_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a car from my garage",
    response_model=None,
)
def delete_car(
    car_id: UUID,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    svc.delete(db, car_id, user.id)


@router.post(
    "/{car_id}/mileage",
    response_model=CarOut,
    summary="Record a new mileage reading",
)
def post_mileage(
    car_id: UUID,
    body: MileageReadingIn,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CarOut:
    return CarOut.from_orm(
        svc.record_mileage(db, car_id, user.id, value=body.value)
    )


@router.get(
    "/{car_id}/recommendations",
    response_model=RecommendationsOut,
    summary="Mileage-based maintenance recommendations",
)
def get_recommendations(
    car_id: UUID,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> RecommendationsOut:
    return RecommendationsOut(**svc.recommendations_for(db, car_id, user.id))
