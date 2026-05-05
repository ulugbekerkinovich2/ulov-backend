"""Services domain logic — intake, queue, state machine, items, photos.

State transitions are the heart of the module:

* ``in_progress`` — sets ``started_at`` if first time.
* ``paused`` — sets ``paused_at``; ``pause_reason`` recorded when given.
* ``in_progress`` from ``paused`` — accumulates the pause window into
  ``paused_elapsed_s`` and clears ``paused_at``.
* ``completed`` — sets ``completed_at``; if from ``paused``, also flushes the
  outstanding pause window.
* ``cancelled`` — sets ``cancelled_at`` + ``cancel_reason``.

All transitions append a row to ``service_transitions`` and emit a domain
event so the WebSocket layer can fan out.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError, ForbiddenError, NotFoundError, UnauthorizedError, ValidationError,
)
from app.core.logging import get_logger
from app.db.base import utcnow
from app.deps import CurrentUser
from app.modules.audit import service as audit_svc
from app.modules.cars import repository as cars_repo
from app.modules.cars.models import Car
from app.modules.mechanics import repository as mech_repo
from app.modules.service_centers import repository as centers_repo
from app.modules.service_centers import service as centers_svc
from app.modules.services import repository as repo
from app.modules.services import state_machine as sm
from app.modules.services.models import ConditionImage, Service, ServiceTransition

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------
def _can_view(service: Service, user: CurrentUser, *, car_owner_id: UUIDLike) -> bool:
    if user.role == "admin":
        return True
    if user.role == "owner":
        # Owner is authorised iff they own the centre. Caller (router) is
        # expected to have already validated centre ownership before reaching
        # bulk listings; for service detail we check explicitly via
        # `assert_view_access`.
        return True
    if user.role == "mechanic":
        return str(user.center_id or "") == str(service.center_id)
    if user.role == "customer":
        return str(car_owner_id) == str(user.id)
    return False


def _assert_can_mutate(
    db: Session, service: Service, user: CurrentUser
) -> None:
    if user.role == "admin":
        return
    if user.role == "mechanic" and str(user.center_id or "") == str(service.center_id):
        return
    if user.role == "owner":
        center = centers_svc.get_or_404(db, service.center_id)
        if str(center.owner_user_id) == str(user.id):
            return
    raise ForbiddenError("No access to this service", code="SERVICE_FORBIDDEN")


def _get_or_404(db: Session, service_id: UUIDLike) -> Service:
    s = repo.get_by_id(db, service_id)
    if s is None:
        raise NotFoundError("Service not found", code="SERVICE_NOT_FOUND")
    return s


def assert_view_access(db: Session, service: Service, user: CurrentUser) -> None:
    if user.role in {"admin"}:
        return
    if user.role == "mechanic" and str(user.center_id or "") == str(service.center_id):
        return
    if user.role == "owner":
        center = centers_svc.get_or_404(db, service.center_id)
        if str(center.owner_user_id) == str(user.id):
            return
    if user.role == "customer":
        car = cars_repo.get_by_id(db, service.car_id)
        if car is not None and str(car.owner_id) == str(user.id):
            return
    raise ForbiddenError("No access to this service", code="SERVICE_FORBIDDEN")


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def get_for_user(db: Session, service_id: UUIDLike, user: CurrentUser) -> Service:
    s = _get_or_404(db, service_id)
    assert_view_access(db, s, user)
    return s


def list_for_center(
    db: Session,
    center_id: UUIDLike,
    user: CurrentUser,
    *,
    statuses: Optional[List[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Service]:
    centers_svc.assert_ops_access(db, center_id, user)
    return repo.list_for_center(
        db,
        center_id,
        statuses=statuses,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


def list_for_car(
    db: Session,
    car_id: UUIDLike,
    user: CurrentUser,
    *,
    limit: int = 100,
    offset: int = 0,
) -> List[Service]:
    # Anyone who can view a single service for this car can list all
    # We'll check car ownership or center access in the repository/service layer
    car = _validate_car(db, car_id)
    # Check if user is staff or owner
    if user.role not in {"mechanic", "owner", "admin"}:
        if str(car.owner_id) != str(user.id):
             raise ForbiddenError("No access to this car history", code="CAR_HISTORY_FORBIDDEN")
    
    return repo.list_for_car(db, car_id, limit=limit, offset=offset)


def list_mine(
    db: Session,
    user: CurrentUser,
    *,
    limit: int = 100,
    offset: int = 0,
) -> List[Service]:
    if user.role != "customer":
         return []
    return repo.list_for_user(db, user.id, limit=limit, offset=offset)


def list_items(db: Session, service_id: UUIDLike, user: CurrentUser):
    s = get_for_user(db, service_id, user)
    return repo.list_items(db, s.id)


def list_timeline(
    db: Session, service_id: UUIDLike, user: CurrentUser
) -> List[ServiceTransition]:
    s = get_for_user(db, service_id, user)
    return repo.list_transitions(db, s.id)


# ---------------------------------------------------------------------------
# Lookup (for intake)
# ---------------------------------------------------------------------------
def lookup_vehicle(
    db: Session,
    user: CurrentUser,
    *,
    vin: Optional[str] = None,
    plate: Optional[str] = None,
):
    """Single-car lookup by VIN or plate. Kept for the intake flow which
    needs exactly one car or a 404. For the staff search UI use
    :func:`search_vehicles` instead.
    """
    if not vin and not plate:
        raise ValidationError(
            "vin or plate required", code="LOOKUP_REQUIRES_VIN_OR_PLATE"
        )
    if user.role not in {"mechanic", "owner", "admin"}:
        raise ForbiddenError("Staff only", code="LOOKUP_STAFF_ONLY")
    car = None
    if vin:
        car = cars_repo.get_by_vin(db, vin)
    if car is None and plate:
        car = cars_repo.get_by_plate(db, plate)
    if car is None:
        raise NotFoundError("Vehicle not found", code="VEHICLE_NOT_FOUND")
    return car


def search_vehicles(
    db: Session,
    user: CurrentUser,
    *,
    vin: Optional[str] = None,
    plate: Optional[str] = None,
    phone: Optional[str] = None,
    tech_passport: Optional[str] = None,
) -> List[Car]:
    """Staff-side vehicle search.

    Accepts any one of VIN, plate, owner phone, or tech-passport number and
    returns *all* matching cars. Phone-based search returns every car
    registered to that owner — one phone can have many vehicles. The other
    three identifiers are unique per car so they return at most one row, but
    we still return a list for a consistent response shape.

    Plate input is normalised (uppercased + non-alnum stripped) before the
    DB lookup so callers can pass ``"01 U 255 ER"`` or ``"01U255ER"`` and get
    the same result. Tech-passport gets the same treatment.
    """
    if not (vin or plate or phone or tech_passport):
        raise ValidationError(
            "vin, plate, phone or tech_passport required",
            code="LOOKUP_REQUIRES_QUERY",
        )
    if user.role not in {"mechanic", "owner", "admin"}:
        raise ForbiddenError("Staff only", code="LOOKUP_STAFF_ONLY")

    if phone:
        from app.core.phone import normalize_phone, PhoneError
        from app.modules.auth import repository as auth_repo

        try:
            normalized = normalize_phone(phone)
        except PhoneError:
            return []
        owner = auth_repo.get_user_by_phone(db, normalized)
        if owner is None:
            return []
        return cars_repo.list_by_owner(db, owner.id)

    cars: List[Car] = []

    if vin:
        # VIN normalisation: strip whitespace and uppercase. We don't enforce
        # a 17-char length here because some legacy rows may store partial
        # VINs.
        normalized_vin = vin.strip().upper().replace(" ", "")
        if normalized_vin:
            c = cars_repo.get_by_vin(db, normalized_vin)
            if c is not None:
                cars.append(c)

    if not cars and plate:
        # Mirror cars/schemas plate normalisation so the staff search isn't
        # picky about spaces / dashes.
        from app.core.plate import _strip as _strip_plate

        normalized_plate = _strip_plate(plate)
        if normalized_plate:
            c = cars_repo.get_by_plate(db, normalized_plate)
            if c is not None:
                cars.append(c)

    if not cars and tech_passport:
        # Tech passport — same alnum-only normalisation as the cars schema's
        # _norm_tech_passport helper.
        normalized_tp = "".join(
            ch for ch in tech_passport.upper() if ch.isalnum()
        )
        if normalized_tp:
            c = cars_repo.get_by_tech_passport(db, normalized_tp)
            if c is not None:
                cars.append(c)

    return cars


# ---------------------------------------------------------------------------
# Create / patch
# ---------------------------------------------------------------------------
def _validate_mechanic_for_center(
    db: Session, center_id: UUIDLike, mechanic_id: Optional[UUIDLike]
) -> None:
    if mechanic_id is None:
        return
    m = mech_repo.get_by_id(db, mechanic_id)
    if m is None or str(m.center_id) != str(center_id):
        raise ValidationError(
            "Mechanic does not belong to this centre",
            code="SERVICE_MECHANIC_INVALID",
        )


def _validate_car(db: Session, car_id: UUIDLike):
    car = cars_repo.get_by_id(db, car_id)
    if car is None:
        raise NotFoundError("Car not found", code="CAR_NOT_FOUND")
    return car


def create(
    db: Session,
    center_id: UUIDLike,
    user: CurrentUser,
    *,
    car_id: UUIDLike,
    mileage_at_intake: int,
    mechanic_id: Optional[UUIDLike] = None,
    next_recommended_mileage: Optional[int] = None,
    notes: Optional[str] = None,
    items: Optional[List[Dict[str, Any]]] = None,
) -> Service:
    centers_svc.assert_ops_access(db, center_id, user)
    car = _validate_car(db, car_id)
    if mileage_at_intake < (car.mileage or 0):
        raise ValidationError(
            "Intake mileage cannot be below the car's recorded mileage",
            code="SERVICE_MILEAGE_REGRESSION",
            details={"current": car.mileage, "submitted": mileage_at_intake},
        )
    _validate_mechanic_for_center(db, center_id, mechanic_id)

    s = repo.create(
        db,
        car_id=car_id,
        center_id=center_id,
        mechanic_id=mechanic_id,
        status=sm.WAITING,
        mileage_at_intake=mileage_at_intake,
        next_recommended_mileage=next_recommended_mileage,
        notes=notes,
    )
    if items:
        repo.replace_items(
            db, s.id, [it.dict() if hasattr(it, "dict") else it for it in items]
        )
    repo.add_transition(
        db,
        service_id=s.id,
        from_status=None,
        to_status=sm.WAITING,
        by_user_id=user.id,
        reason=None,
    )
    # Snap the intake mileage onto the car + history.
    if mileage_at_intake > (car.mileage or 0):
        cars_repo.update_fields(db, car.id, mileage=mileage_at_intake)
        cars_repo.append_mileage_reading(
            db, car_id=car.id, value=mileage_at_intake, source="service"
        )
    log.info(
        "service_created",
        service_id=str(s.id),
        center_id=str(center_id),
        car_id=str(car_id),
    )
    return s


def book_by_customer(
    db: Session,
    center_id: UUIDLike,
    user: CurrentUser,
    *,
    car_id: UUIDLike,
    items: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[str] = None,
) -> Service:
    """Customer-initiated booking: opens a service in ``waiting`` so the
    centre's queue picks it up. The car must belong to the calling user;
    no centre staff role is required.
    """
    car = _validate_car(db, car_id)
    if str(car.owner_id) != str(user.id) and user.role != "admin":
        raise UnauthorizedError(
            "Not your car", code="SERVICE_BOOKING_NOT_OWNER"
        )

    center = centers_repo.get_by_id(db, center_id)
    if center is None:
        raise NotFoundError("Centre not found", code="CENTER_NOT_FOUND")

    s = repo.create(
        db,
        car_id=car.id,
        center_id=center.id,
        mechanic_id=None,
        status=sm.WAITING,
        mileage_at_intake=car.mileage or 0,
        next_recommended_mileage=None,
        notes=notes,
    )
    if items:
        repo.replace_items(
            db, s.id, [it.dict() if hasattr(it, "dict") else it for it in items]
        )
    repo.add_transition(
        db,
        service_id=s.id,
        from_status=None,
        to_status=sm.WAITING,
        by_user_id=user.id,
        reason="customer_booking",
    )
    log.info(
        "service_booked_by_customer",
        service_id=str(s.id),
        center_id=str(center.id),
        car_id=str(car.id),
        user_id=str(user.id),
    )
    return s


def patch(
    db: Session,
    service_id: UUIDLike,
    user: CurrentUser,
    data: Dict[str, Any],
) -> Service:
    s = _get_or_404(db, service_id)
    _assert_can_mutate(db, s, user)
    if s.status in sm.TERMINAL:
        raise ConflictError(
            f"Service is {s.status}; cannot edit",
            code="SERVICE_TERMINAL_LOCKED",
        )

    payload: Dict[str, Any] = {}
    if "mechanic_id" in data:
        _validate_mechanic_for_center(db, s.center_id, data["mechanic_id"])
        payload["mechanic_id"] = data["mechanic_id"]
    if "next_recommended_mileage" in data and data["next_recommended_mileage"] is not None:
        payload["next_recommended_mileage"] = data["next_recommended_mileage"]
    if "notes" in data and data["notes"] is not None:
        payload["notes"] = data["notes"]

    if payload:
        repo.update_fields(db, s.id, **payload)

    if "items" in data and data["items"] is not None:
        repo.replace_items(
            db, s.id, [it.dict() if hasattr(it, "dict") else it for it in data["items"]]
        )

    return _get_or_404(db, s.id)


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------
def transition(
    db: Session,
    service_id: UUIDLike,
    user: CurrentUser,
    *,
    to_status: str,
    reason: Optional[str] = None,
) -> Tuple[Service, ServiceTransition]:
    s = _get_or_404(db, service_id)
    _assert_can_mutate(db, s, user)
    sm.validate(s.status, to_status, reason=reason)

    now = utcnow()
    fields: Dict[str, Any] = {"status": to_status}
    from_status = s.status

    if to_status == sm.IN_PROGRESS:
        if from_status == sm.WAITING:
            fields["started_at"] = s.started_at or now
        if from_status == sm.PAUSED and s.paused_at is not None:
            elapsed = int((now - s.paused_at).total_seconds())
            if elapsed > 0:
                fields["paused_elapsed_s"] = (s.paused_elapsed_s or 0) + elapsed
            fields["paused_at"] = None

    elif to_status == sm.PAUSED:
        fields["paused_at"] = now
        fields["pause_reason"] = (reason or "").strip() or None

    elif to_status == sm.COMPLETED:
        if from_status == sm.PAUSED and s.paused_at is not None:
            elapsed = int((now - s.paused_at).total_seconds())
            if elapsed > 0:
                fields["paused_elapsed_s"] = (s.paused_elapsed_s or 0) + elapsed
            fields["paused_at"] = None
        fields["completed_at"] = now

    elif to_status == sm.CANCELLED:
        fields["cancelled_at"] = now
        fields["cancel_reason"] = (reason or "").strip()

    repo.update_fields(db, s.id, **fields)
    transition_row = repo.add_transition(
        db,
        service_id=s.id,
        from_status=from_status,
        to_status=to_status,
        by_user_id=user.id,
        reason=reason,
    )
    log.info(
        "service_transitioned",
        service_id=str(s.id),
        from_status=from_status,
        to_status=to_status,
    )
    audit_svc.record(
        db,
        actor=user,
        action="service.transitioned",
        entity_type="service",
        entity_id=s.id,
        before={"status": from_status},
        after={"status": to_status},
        meta={"reason": reason} if reason else None,
    )
    return _get_or_404(db, s.id), transition_row


# ---------------------------------------------------------------------------
# Condition photos
# ---------------------------------------------------------------------------
def add_condition_photo(
    db: Session,
    service_id: UUIDLike,
    user: CurrentUser,
    *,
    url: str,
    stage: str,
) -> ConditionImage:
    s = _get_or_404(db, service_id)
    _assert_can_mutate(db, s, user)
    return repo.add_condition_image(
        db, service_id=s.id, url=url, stage=stage, uploaded_by=user.id
    )
