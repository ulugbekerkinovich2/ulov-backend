"""Trips endpoints."""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_customer, get_db
from app.modules.trips import service as svc
from app.modules.trips.schemas import (
    TripOut,
    TripPointsBatchIn,
    TripStartIn,
)

router = APIRouter()


@router.post(
    "",
    response_model=TripOut,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new trip",
)
def start_trip(
    body: TripStartIn,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> TripOut:
    trip = svc.start(db, user.id, car_id=body.car_id)
    return TripOut.from_orm(trip)


@router.post(
    "/{trip_id}/points",
    summary="Append a batch of GPS points",
)
def append_points(
    trip_id: UUID,
    body: TripPointsBatchIn,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> dict:
    n = svc.append_points(
        db, trip_id, user.id, points=[p.dict() for p in body.points]
    )
    return {"appended": n}


@router.post(
    "/{trip_id}/finish",
    response_model=TripOut,
    summary="Finalise the trip and compute distance/duration/avg_speed",
)
def finish_trip(
    trip_id: UUID,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> TripOut:
    return TripOut.from_orm(svc.finish(db, trip_id, user.id))


@router.get("", response_model=List[TripOut], summary="List my trips")
def list_my_trips(
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> List[TripOut]:
    return [TripOut.from_orm(t) for t in svc.list_for_user(db, user.id)]
