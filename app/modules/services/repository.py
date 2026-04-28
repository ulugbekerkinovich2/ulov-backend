"""Services repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, List, Optional, Union
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.modules.services.models import (
    ConditionImage,
    Service,
    ServiceItem,
    ServiceTransition,
)

UUIDLike = Union[UUID, str]


# ---- Services --------------------------------------------------------------
def create(db: Session, **fields: Any) -> Service:
    s = Service(**fields)
    db.add(s)
    db.flush()
    return s


def get_by_id(
    db: Session, service_id: UUIDLike, *, include_deleted: bool = False
) -> Optional[Service]:
    stmt = select(Service).where(Service.id == service_id)
    if not include_deleted:
        stmt = stmt.where(Service.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def update_fields(
    db: Session, service_id: UUIDLike, **fields: Any
) -> Optional[Service]:
    if not fields:
        return get_by_id(db, service_id)
    db.execute(
        update(Service)
        .where(Service.id == service_id)
        .values(**fields)
    )
    db.flush()
    return get_by_id(db, service_id, include_deleted=True)


def list_for_center(
    db: Session,
    center_id: UUIDLike,
    *,
    statuses: Optional[Iterable[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Service]:
    stmt = (
        select(Service)
        .where(Service.center_id == center_id)
        .where(Service.deleted_at.is_(None))
    )
    if statuses:
        stmt = stmt.where(Service.status.in_(list(statuses)))
    if date_from:
        stmt = stmt.where(Service.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Service.created_at <= date_to)
    stmt = stmt.order_by(Service.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars())


def list_for_car(
    db: Session,
    car_id: UUIDLike,
    *,
    limit: int = 100,
    offset: int = 0,
) -> List[Service]:
    stmt = (
        select(Service)
        .where(Service.car_id == car_id)
        .where(Service.deleted_at.is_(None))
        .order_by(Service.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars())


def list_for_user(db: Session, user_id: UUIDLike, limit: int = 100, offset: int = 0) -> List[Service]:
    from app.modules.cars.models import Car
    stmt = (
        select(Service)
        .join(Car, Service.car_id == Car.id)
        .where(Car.owner_id == user_id)
        .where(Service.deleted_at.is_(None))
        .order_by(Service.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars())


# ---- Items -----------------------------------------------------------------
def list_items(db: Session, service_id: UUIDLike) -> List[ServiceItem]:
    stmt = (
        select(ServiceItem)
        .where(ServiceItem.service_id == service_id)
        .order_by(ServiceItem.created_at)
    )
    return list(db.execute(stmt).scalars())


def add_item(db: Session, service_id: UUIDLike, **fields: Any) -> ServiceItem:
    item = ServiceItem(service_id=service_id, **fields)
    db.add(item)
    db.flush()
    return item


def replace_items(
    db: Session, service_id: UUIDLike, items: List[dict]
) -> List[ServiceItem]:
    db.execute(delete(ServiceItem).where(ServiceItem.service_id == service_id))
    out: List[ServiceItem] = []
    for it in items:
        out.append(add_item(db, service_id, **it))
    return out


# ---- Transitions -----------------------------------------------------------
def add_transition(
    db: Session,
    *,
    service_id: UUIDLike,
    from_status: Optional[str],
    to_status: str,
    by_user_id: Optional[UUIDLike],
    reason: Optional[str],
) -> ServiceTransition:
    t = ServiceTransition(
        service_id=service_id,
        from_status=from_status,
        to_status=to_status,
        by_user_id=by_user_id,
        reason=reason,
    )
    db.add(t)
    db.flush()
    return t


def list_transitions(
    db: Session, service_id: UUIDLike
) -> List[ServiceTransition]:
    stmt = (
        select(ServiceTransition)
        .where(ServiceTransition.service_id == service_id)
        .order_by(ServiceTransition.at)
    )
    return list(db.execute(stmt).scalars())


# ---- Photos ----------------------------------------------------------------
def add_condition_image(
    db: Session,
    *,
    service_id: UUIDLike,
    url: str,
    stage: str,
    uploaded_by: Optional[UUIDLike],
) -> ConditionImage:
    img = ConditionImage(
        service_id=service_id,
        url=url,
        stage=stage,
        uploaded_by=uploaded_by,
    )
    db.add(img)
    db.flush()
    return img


def list_condition_images(
    db: Session, service_id: UUIDLike
) -> List[ConditionImage]:
    stmt = (
        select(ConditionImage)
        .where(ConditionImage.service_id == service_id)
        .order_by(ConditionImage.at)
    )
    return list(db.execute(stmt).scalars())
