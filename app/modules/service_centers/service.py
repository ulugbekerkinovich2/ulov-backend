"""Service centre domain logic.

Rules:
  * Only the centre's owner (or admin) may mutate it.
  * ``location`` round-trips as {lat, lng}; stored as PostGIS point.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.deps import CurrentUser
from app.modules.service_centers import repository as repo
from app.modules.service_centers.models import ServiceCenter

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


def location_to_dict(center: ServiceCenter) -> Optional[Dict[str, float]]:
    loc = center.location
    if loc is None or not isinstance(loc, dict):
        return None
    if "lat" not in loc or "lng" not in loc:
        return None
    try:
        return {"lat": float(loc["lat"]), "lng": float(loc["lng"])}
    except (TypeError, ValueError):
        return None


def _assert_can_mutate(center: ServiceCenter, user: CurrentUser) -> None:
    if user.is_owner and user.role == "admin":
        return
    if str(center.owner_user_id) != str(user.id):
        raise ForbiddenError("Not your centre", code="CENTER_NOT_OWNER")


def _can_view_center_ops(center: ServiceCenter, user: CurrentUser) -> bool:
    """Can the user see queue/mechanics/services for this centre?"""
    if user.role == "admin":
        return True
    if str(center.owner_user_id) == str(user.id):
        return True
    # Mechanic bound to this centre via JWT claim.
    if user.role == "mechanic" and str(user.center_id or "") == str(center.id):
        return True
    return False


def get_or_404(db: Session, center_id: UUIDLike) -> ServiceCenter:
    c = repo.get_by_id(db, center_id)
    if c is None:
        raise NotFoundError("Service centre not found", code="CENTER_NOT_FOUND")
    return c


def assert_ops_access(db: Session, center_id: UUIDLike, user: CurrentUser) -> ServiceCenter:
    c = get_or_404(db, center_id)
    if not _can_view_center_ops(c, user):
        raise ForbiddenError("No access to this centre", code="CENTER_FORBIDDEN")
    return c


def create(db: Session, user: CurrentUser, data: Dict[str, Any]) -> ServiceCenter:
    if not user.is_owner:
        raise ForbiddenError("Only owners may create centres", code="CENTER_REQUIRES_OWNER")
    loc = data.get("location")
    if loc is not None and not isinstance(loc, dict):
        loc = loc.dict()
    center = repo.create(
        db,
        owner_user_id=user.id,
        name=data["name"],
        phone=data["phone"],
        address=data["address"],
        description=data.get("description"),
        location=loc,
        schedule=data.get("schedule") or {},
        services=data.get("services") or [],
        avatar_url=data.get("avatar_url"),
    )
    log.info("center_created", center_id=str(center.id), owner=str(user.id))
    return center


def patch(
    db: Session, center_id: UUIDLike, user: CurrentUser, data: Dict[str, Any]
) -> ServiceCenter:
    center = get_or_404(db, center_id)
    _assert_can_mutate(center, user)

    payload: Dict[str, Any] = {}
    for k in ("name", "phone", "address", "description", "avatar_url", "schedule", "services"):
        if k in data and data[k] is not None:
            payload[k] = data[k]

    if "location" in data:
        loc = data["location"]
        payload["location"] = loc.dict() if hasattr(loc, "dict") else loc

    updated = repo.update_fields(db, center_id, **payload)
    assert updated is not None
    log.info("center_updated", center_id=str(center.id), fields=list(payload.keys()))
    return updated


def delete(db: Session, center_id: UUIDLike, user: CurrentUser) -> None:
    center = get_or_404(db, center_id)
    _assert_can_mutate(center, user)
    repo.remove(db, center_id)
    log.info("center_deleted", center_id=str(center.id))


def list_mine(db: Session, user: CurrentUser) -> List[ServiceCenter]:
    if user.role == "admin":
        return repo.list_all(db)
    return repo.list_by_owner(db, user.id)


def nearby(
    db: Session, *, lat: float, lng: float, radius_m: int, limit: int
) -> List[Tuple[ServiceCenter, float]]:
    return repo.find_nearby(db, lat=lat, lng=lng, radius_m=radius_m, limit=limit)
