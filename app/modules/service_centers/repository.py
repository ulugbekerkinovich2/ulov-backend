"""Service centres repository.

``location`` is JSONB ``{lat, lng}`` — we filter / sort in Python rather
than rely on PostGIS so the local dev image stays portable across hosts.
"""

from __future__ import annotations

import math
from typing import Any, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.modules.service_centers.models import ServiceCenter

UUIDLike = Union[UUID, str]


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _location_payload(loc: Optional[dict]) -> Optional[dict]:
    if loc is None:
        return None
    if not isinstance(loc, dict):
        return None
    if "lat" not in loc or "lng" not in loc:
        return None
    return {"lat": float(loc["lat"]), "lng": float(loc["lng"])}


def create(db: Session, **fields: Any) -> ServiceCenter:
    loc = fields.pop("location", None)
    if loc is not None:
        fields["location"] = _location_payload(loc)
    center = ServiceCenter(**fields)
    db.add(center)
    db.flush()
    return center


def get_by_id(db: Session, center_id: UUIDLike) -> Optional[ServiceCenter]:
    return db.execute(
        select(ServiceCenter).where(ServiceCenter.id == center_id)
    ).scalar_one_or_none()


def list_by_owner(db: Session, owner_id: UUIDLike) -> List[ServiceCenter]:
    stmt = (
        select(ServiceCenter)
        .where(ServiceCenter.owner_user_id == owner_id)
        .order_by(ServiceCenter.created_at)
    )
    return list(db.execute(stmt).scalars())


def list_all(db: Session, *, limit: int = 100, offset: int = 0) -> List[ServiceCenter]:
    stmt = (
        select(ServiceCenter)
        .order_by(ServiceCenter.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars())


def update_fields(db: Session, center_id: UUIDLike, **fields: Any) -> Optional[ServiceCenter]:
    loc = fields.pop("location", ...)
    clean = {k: v for k, v in fields.items() if v is not None}
    if loc is not ...:
        clean["location"] = _location_payload(loc) if loc else None
    if clean:
        db.execute(update(ServiceCenter).where(ServiceCenter.id == center_id).values(**clean))
        db.flush()
    # populate_existing — see cars.repository.update_fields. Without it
    # the ORM hands back the pre-update cached row.
    stmt = (
        select(ServiceCenter)
        .where(ServiceCenter.id == center_id)
        .execution_options(populate_existing=True)
    )
    return db.execute(stmt).scalar_one_or_none()


def remove(db: Session, center_id: UUIDLike) -> int:
    result = db.execute(delete(ServiceCenter).where(ServiceCenter.id == center_id))
    return int(result.rowcount or 0)


def find_nearby(
    db: Session, *, lat: float, lng: float, radius_m: int, limit: int
) -> List[Tuple[ServiceCenter, float]]:
    """Return centres within ``radius_m``, ordered by distance (m)."""
    rows = db.execute(select(ServiceCenter)).scalars().all()
    out: List[Tuple[ServiceCenter, float]] = []
    for c in rows:
        loc = c.location if isinstance(c.location, dict) else None
        if loc is None or "lat" not in loc or "lng" not in loc:
            continue
        d = _haversine_m(lat, lng, float(loc["lat"]), float(loc["lng"]))
        if d <= radius_m:
            out.append((c, d))
    out.sort(key=lambda r: r[1])
    return out[:limit]
