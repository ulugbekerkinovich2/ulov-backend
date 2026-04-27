"""Mechanics domain logic.

Owners manage mechanics scoped to their centres. Login uniqueness is global
(it is the credential a mechanic uses to authenticate) so duplicates are 409.
"""

from __future__ import annotations

from typing import Any, Dict, List, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.deps import CurrentUser
from app.modules.mechanics import repository as repo
from app.modules.mechanics.models import Mechanic
from app.modules.service_centers import service as centers_svc

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


def _assert_center_admin(db: Session, center_id: UUIDLike, user: CurrentUser) -> None:
    """Owner of centre or admin only."""
    center = centers_svc.get_or_404(db, center_id)
    if user.role == "admin":
        return
    if str(center.owner_user_id) != str(user.id):
        raise ForbiddenError("Not your centre", code="CENTER_NOT_OWNER")


def _get_owned(
    db: Session, mechanic_id: UUIDLike, user: CurrentUser
) -> Mechanic:
    m = repo.get_by_id(db, mechanic_id)
    if m is None:
        raise NotFoundError("Mechanic not found", code="MECHANIC_NOT_FOUND")
    _assert_center_admin(db, m.center_id, user)
    return m


def list_for_center(
    db: Session, center_id: UUIDLike, user: CurrentUser
) -> List[Mechanic]:
    centers_svc.assert_ops_access(db, center_id, user)
    return repo.list_by_center(db, center_id)


def create(
    db: Session, center_id: UUIDLike, user: CurrentUser, data: Dict[str, Any]
) -> Mechanic:
    _assert_center_admin(db, center_id, user)
    if repo.get_by_login(db, data["login"]) is not None:
        raise ConflictError("Login already taken", code="MECHANIC_LOGIN_DUPLICATE")
    m = repo.create(
        db,
        center_id=center_id,
        full_name=data["full_name"],
        login=data["login"],
        password_hash=hash_password(data["password"]),
        service_types=data.get("service_types") or [],
    )
    log.info("mechanic_created", mechanic_id=str(m.id), center_id=str(center_id))
    return m


def patch(
    db: Session, mechanic_id: UUIDLike, user: CurrentUser, data: Dict[str, Any]
) -> Mechanic:
    m = _get_owned(db, mechanic_id, user)
    payload: Dict[str, Any] = {}
    if data.get("full_name") is not None:
        payload["full_name"] = data["full_name"]
    if data.get("service_types") is not None:
        payload["service_types"] = data["service_types"]
    if data.get("password"):
        payload["password_hash"] = hash_password(data["password"])
    updated = repo.update_fields(db, mechanic_id, **payload)
    assert updated is not None
    log.info("mechanic_updated", mechanic_id=str(m.id), fields=list(payload.keys()))
    return updated


def delete(db: Session, mechanic_id: UUIDLike, user: CurrentUser) -> None:
    m = _get_owned(db, mechanic_id, user)
    repo.soft_delete(db, mechanic_id)
    log.info("mechanic_deleted", mechanic_id=str(m.id))
