"""Platform-staff endpoints (cross-tenant read + light write).

Everything here requires ``Role.ADMIN``. The intent is one place where
operations / support can see the whole platform without going through
centre-scoped endpoints. We keep the surface deliberately small for now.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.rbac import Role, require_role
from app.deps import CurrentUser, get_db
from app.modules.audit import service as audit_svc
from app.modules.cars.models import Car
from app.modules.service_centers.models import ServiceCenter
from app.modules.services.models import Service
from app.modules.users.models import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Platform overview
# ---------------------------------------------------------------------------
@router.get(
    "/admin/overview",
    response_model=Dict[str, Any],
    summary="Platform-wide KPIs",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def overview(db: Session = Depends(get_db)) -> Dict[str, Any]:
    by_role = dict(
        db.execute(select(User.role, func.count()).group_by(User.role)).all()
    )
    return {
        "users": int(db.execute(select(func.count(User.id))).scalar_one()),
        "by_role": {k: int(v) for k, v in by_role.items()},
        "centres": int(db.execute(select(func.count(ServiceCenter.id))).scalar_one()),
        "cars": int(db.execute(select(func.count(Car.id))).scalar_one()),
        "services": int(
            db.execute(
                select(func.count(Service.id)).where(Service.deleted_at.is_(None))
            ).scalar_one()
        ),
        "active_services": int(
            db.execute(
                select(func.count(Service.id))
                .where(Service.deleted_at.is_(None))
                .where(Service.status.in_(("waiting", "in_progress", "paused")))
            ).scalar_one()
        ),
    }


# ---------------------------------------------------------------------------
# Users — admin can list + flip role + (de)activate
# ---------------------------------------------------------------------------
@router.get(
    "/admin/users",
    response_model=List[Dict[str, Any]],
    summary="Browse users platform-wide",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def list_users(
    role: Optional[str] = Query(None, regex="^(customer|mechanic|owner|admin)$"),
    q: Optional[str] = Query(None, max_length=100, description="Phone substring"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        stmt = stmt.where(User.phone.ilike(f"%{q}%"))
    rows = db.execute(stmt).scalars()
    return [
        {
            "id": str(u.id),
            "phone": u.phone,
            "full_name": u.full_name,
            "email": u.email,
            "city": u.city,
            "role": u.role,
            "center_id": str(u.center_id) if u.center_id else None,
            "is_active": bool(u.is_active),
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in rows
    ]


@router.post(
    "/admin/users/{user_id}/role",
    response_model=Dict[str, Any],
    summary="Promote / demote a user",
)
def change_role(
    user_id: UUID,
    body: Dict[str, str],
    actor: CurrentUser = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    new_role = body.get("role")
    if new_role not in {"customer", "mechanic", "owner", "admin"}:
        raise ValidationError("invalid role", code="ADMIN_ROLE_INVALID")
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    before = {"role": user.role}
    user.role = new_role
    db.flush()
    audit_svc.record(
        db,
        actor=actor,
        action="user.role_changed",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after={"role": user.role},
    )
    return {"id": str(user.id), "role": user.role}


@router.post(
    "/admin/users/{user_id}/active",
    response_model=Dict[str, Any],
    summary="Activate / deactivate a user",
)
def set_active(
    user_id: UUID,
    body: Dict[str, bool],
    actor: CurrentUser = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    is_active = bool(body.get("is_active", True))
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    before = {"is_active": bool(user.is_active)}
    user.is_active = is_active
    db.flush()
    audit_svc.record(
        db,
        actor=actor,
        action="user.active_changed",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after={"is_active": is_active},
    )
    return {"id": str(user.id), "is_active": is_active}


# ---------------------------------------------------------------------------
# Centres — admin sees them all
# ---------------------------------------------------------------------------
@router.get(
    "/admin/service-centers",
    response_model=List[Dict[str, Any]],
    summary="All service centres",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def list_centres(
    q: Optional[str] = Query(None, max_length=100),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    stmt = (
        select(ServiceCenter)
        .order_by(ServiceCenter.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if q:
        stmt = stmt.where(ServiceCenter.name.ilike(f"%{q}%"))
    rows = db.execute(stmt).scalars()
    return [
        {
            "id": str(c.id),
            "owner_user_id": str(c.owner_user_id),
            "name": c.name,
            "phone": c.phone,
            "address": c.address,
            "subscription_until": c.subscription_until,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]
