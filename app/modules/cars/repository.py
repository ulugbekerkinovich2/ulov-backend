"""Cars repository — owns access to the ``cars`` + ``mileage_readings`` tables."""

from __future__ import annotations

import time
from typing import Any, List, Optional, Union
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.modules.cars.models import Car, MileageReading

UUIDLike = Union[UUID, str]


# ---- Cars ------------------------------------------------------------------
def list_by_owner(db: Session, owner_id: UUIDLike) -> List[Car]:
    stmt = select(Car).where(Car.owner_id == owner_id).order_by(Car.created_at)
    return list(db.execute(stmt).scalars())


def get_by_id(db: Session, car_id: UUIDLike) -> Optional[Car]:
    return db.execute(select(Car).where(Car.id == car_id)).scalar_one_or_none()


def get_by_plate(db: Session, plate: str) -> Optional[Car]:
    return db.execute(select(Car).where(Car.plate == plate)).scalar_one_or_none()


def get_by_vin(db: Session, vin: str) -> Optional[Car]:
    return db.execute(select(Car).where(Car.vin == vin)).scalar_one_or_none()


def create(db: Session, **fields: Any) -> Car:
    car = Car(**fields)
    db.add(car)
    db.flush()
    return car


def update_fields(db: Session, car_id: UUIDLike, **fields: Any) -> Optional[Car]:
    clean = {k: v for k, v in fields.items() if v is not None}
    if clean:
        db.execute(update(Car).where(Car.id == car_id).values(**clean))
        db.flush()
    return get_by_id(db, car_id)


def remove(db: Session, car_id: UUIDLike) -> int:
    result = db.execute(delete(Car).where(Car.id == car_id))
    return int(result.rowcount or 0)


# ---- Mileage readings ------------------------------------------------------
def append_mileage_reading(
    db: Session, *, car_id: UUIDLike, value: int, source: str = "user"
) -> MileageReading:
    reading = MileageReading(
        car_id=car_id,
        value=value,
        source=source,
        recorded_at=int(time.time() * 1000),
    )
    db.add(reading)
    db.flush()
    return reading


def last_mileage(db: Session, car_id: UUIDLike) -> Optional[int]:
    stmt = (
        select(MileageReading.value)
        .where(MileageReading.car_id == car_id)
        .order_by(MileageReading.recorded_at.desc())
        .limit(1)
    )
    row = db.execute(stmt).scalar_one_or_none()
    return int(row) if row is not None else None
