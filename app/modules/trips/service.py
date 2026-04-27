"""Trips domain logic — start, append GPS, finish, list."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, List, Optional, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.modules.trips.models import Trip, TripPoint

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------
def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def _get_owned(db: Session, trip_id: UUIDLike, user_id: UUIDLike) -> Trip:
    trip = db.execute(select(Trip).where(Trip.id == trip_id)).scalar_one_or_none()
    if trip is None:
        raise NotFoundError("Trip not found", code="TRIP_NOT_FOUND")
    if str(trip.user_id) != str(user_id):
        raise ForbiddenError("Not your trip", code="TRIP_NOT_OWNER")
    return trip


def start(
    db: Session, user_id: UUIDLike, *, car_id: Optional[UUIDLike]
) -> Trip:
    trip = Trip(user_id=user_id, car_id=car_id)
    db.add(trip)
    db.flush()
    log.info("trip_started", trip_id=str(trip.id), user_id=str(user_id))
    return trip


def append_points(
    db: Session,
    trip_id: UUIDLike,
    user_id: UUIDLike,
    *,
    points: List[dict],
) -> int:
    trip = _get_owned(db, trip_id, user_id)
    if trip.finished_at is not None:
        raise ConflictError("Trip already finished", code="TRIP_FINISHED")
    rows = [
        TripPoint(
            trip_id=trip.id,
            lat=p["lat"],
            lng=p["lng"],
            speed=p.get("speed"),
            heading=p.get("heading"),
            ts=p.get("ts") or datetime.now(tz=timezone.utc),
        )
        for p in points
    ]
    db.add_all(rows)
    db.flush()
    return len(rows)


def finish(db: Session, trip_id: UUIDLike, user_id: UUIDLike) -> Trip:
    trip = _get_owned(db, trip_id, user_id)
    if trip.finished_at is not None:
        return trip

    pts: Iterable[TripPoint] = db.execute(
        select(TripPoint)
        .where(TripPoint.trip_id == trip.id)
        .order_by(TripPoint.ts)
    ).scalars()
    pts_list = list(pts)
    distance = 0.0
    if len(pts_list) >= 2:
        for a, b in zip(pts_list, pts_list[1:]):
            distance += _haversine_km(a.lat, a.lng, b.lat, b.lng)

    finished = datetime.now(tz=timezone.utc)
    duration = int((finished - trip.started_at).total_seconds())
    avg_speed = (distance / (duration / 3600.0)) if duration > 0 else 0.0

    trip.finished_at = finished
    trip.distance_km = Decimal(f"{distance:.3f}")
    trip.duration_s = duration
    trip.avg_speed = Decimal(f"{avg_speed:.2f}")
    # Rough estimate: 7 L per 100 km.
    trip.fuel_l_est = Decimal(f"{(distance * 0.07):.3f}")
    db.flush()
    log.info(
        "trip_finished",
        trip_id=str(trip.id),
        distance_km=float(trip.distance_km),
        duration_s=trip.duration_s,
    )
    return trip


def list_for_user(db: Session, user_id: UUIDLike, *, limit: int = 50) -> List[Trip]:
    return list(
        db.execute(
            select(Trip)
            .where(Trip.user_id == user_id)
            .order_by(Trip.started_at.desc())
            .limit(limit)
        ).scalars()
    )
