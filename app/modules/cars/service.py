"""Cars domain logic.

Rules enforced here (not at the schema / repository layers):
  * plate uniqueness across **all** users (one plate, one car — intuitive)
  * VIN uniqueness (same rule)
  * mileage is monotonically non-decreasing per car
  * plate_type is persisted from the value the schema detected
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.plate import PlateType, detect_plate_type
from app.modules.cars import recommendations as recs
from app.modules.cars import repository as repo
from app.modules.cars.models import Car

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


# ---- helpers ---------------------------------------------------------------
def _assert_ownership(car: Car, owner_id: UUIDLike) -> None:
    if str(car.owner_id) != str(owner_id):
        raise ForbiddenError("Not your car", code="CAR_NOT_OWNER")


def _check_unique_plate(db: Session, plate: str, *, ignore_id: Optional[UUIDLike] = None) -> None:
    existing = repo.get_by_plate(db, plate)
    if existing and (ignore_id is None or str(existing.id) != str(ignore_id)):
        raise ConflictError("Plate already registered", code="CAR_PLATE_DUPLICATE")


def _check_unique_vin(db: Session, vin: Optional[str], *, ignore_id: Optional[UUIDLike] = None) -> None:
    if not vin:
        return
    existing = repo.get_by_vin(db, vin)
    if existing and (ignore_id is None or str(existing.id) != str(ignore_id)):
        raise ConflictError("VIN already registered", code="CAR_VIN_DUPLICATE")


# ---- commands --------------------------------------------------------------
def list_mine(db: Session, owner_id: UUIDLike) -> List[Car]:
    return repo.list_by_owner(db, owner_id)


def get_owned(db: Session, car_id: UUIDLike, owner_id: UUIDLike) -> Car:
    car = repo.get_by_id(db, car_id)
    if car is None:
        raise NotFoundError("Car not found", code="CAR_NOT_FOUND")
    _assert_ownership(car, owner_id)
    return car


def create(db: Session, owner_id: UUIDLike, data: Dict[str, Any]) -> Car:
    plate = data["plate"]
    plate_type = data.get("plate_type") or detect_plate_type(plate).value
    _check_unique_plate(db, plate)
    _check_unique_vin(db, data.get("vin"))

    # Normalise plate_type to a string for the enum column.
    if isinstance(plate_type, PlateType):
        plate_type = plate_type.value

    car = repo.create(
        db,
        owner_id=owner_id,
        brand=data["brand"],
        model=data["model"],
        year=data["year"],
        color=data.get("color"),
        plate=plate,
        plate_type=plate_type,
        mileage=int(data.get("mileage", 0) or 0),
        vin=data.get("vin"),
        tech_passport=data.get("tech_passport"),
        insurance_from=data.get("insurance_from"),
        insurance_to=data.get("insurance_to"),
        insurance_company=data.get("insurance_company"),
        tint_from=data.get("tint_from"),
        tint_to=data.get("tint_to"),
        photo_url=data.get("photo_url"),
    )
    # Seed the mileage history with the initial value.
    if car.mileage > 0:
        repo.append_mileage_reading(db, car_id=car.id, value=car.mileage, source="user")
    log.info("car_created", car_id=str(car.id), owner=str(owner_id), plate=plate)
    return car


def patch(db: Session, car_id: UUIDLike, owner_id: UUIDLike, data: Dict[str, Any]) -> Car:
    car = get_owned(db, car_id, owner_id)

    new_plate = data.get("plate")
    if new_plate is not None and new_plate != car.plate:
        _check_unique_plate(db, new_plate, ignore_id=car.id)

    new_vin = data.get("vin")
    if new_vin is not None and new_vin != car.vin:
        _check_unique_vin(db, new_vin, ignore_id=car.id)

    new_mileage = data.get("mileage")
    if new_mileage is not None and new_mileage < car.mileage:
        raise ValidationError(
            "Mileage cannot decrease",
            code="CAR_MILEAGE_DECREASE",
            details={"current": car.mileage, "submitted": new_mileage},
        )

    pt = data.get("plate_type")
    if isinstance(pt, PlateType):
        data["plate_type"] = pt.value

    updated = repo.update_fields(db, car_id, **data)
    assert updated is not None  # we just fetched it

    if new_mileage is not None and new_mileage != car.mileage:
        repo.append_mileage_reading(
            db, car_id=car.id, value=new_mileage, source="user"
        )

    log.info("car_updated", car_id=str(car.id), fields=list(data.keys()))
    return updated


def delete(db: Session, car_id: UUIDLike, owner_id: UUIDLike) -> None:
    car = get_owned(db, car_id, owner_id)
    repo.remove(db, car.id)
    log.info("car_deleted", car_id=str(car.id), owner=str(owner_id))


def record_mileage(
    db: Session, car_id: UUIDLike, owner_id: UUIDLike, *, value: int
) -> Car:
    car = get_owned(db, car_id, owner_id)
    if value < car.mileage:
        raise ValidationError(
            "Mileage cannot decrease",
            code="CAR_MILEAGE_DECREASE",
            details={"current": car.mileage, "submitted": value},
        )
    if value == car.mileage:
        # No-op but still record the reading for the audit trail? We skip to
        # keep the history clean.
        return car
    updated = repo.update_fields(db, car_id, mileage=value)
    assert updated is not None
    repo.append_mileage_reading(db, car_id=car.id, value=value, source="user")
    return updated


def recommendations_for(db: Session, car_id: UUIDLike, owner_id: UUIDLike) -> Dict[str, Any]:
    car = get_owned(db, car_id, owner_id)
    return {
        "car_id": car.id,
        "mileage": car.mileage,
        "items": recs.compute(car.mileage),
    }
