"""Users endpoints — /me read/update + avatar stub."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.deps import CurrentUser, get_current_user, get_db
from app.modules.mechanics.models import Mechanic
from app.modules.users import service as svc
from app.modules.users.schemas import AvatarIn, MeOut, MePatchIn

router = APIRouter()


@router.get("/me", response_model=MeOut, summary="Current user profile")
def get_me(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeOut:
    # Mechanics aren't ``users`` rows — they live in their own table — so we
    # synthesise a MeOut from the Mechanic record. The frontend treats this
    # the same shape as a real user (avatar_url etc. are nullable).
    if user.role == "mechanic":
        mech = db.execute(
            select(Mechanic).where(Mechanic.id == user.id)
        ).scalar_one_or_none()
        if mech is None:
            raise NotFoundError("Mechanic not found", code="MECHANIC_NOT_FOUND")
        return MeOut(
            id=mech.id,
            phone=mech.login,  # login is the closest analogue
            full_name=mech.full_name,
            email=None,
            city=None,
            avatar_url=None,
            role="mechanic",
            center_id=mech.center_id,
            is_active=mech.deleted_at is None,
            created_at=mech.created_at,
            updated_at=mech.created_at,
        )
    return MeOut.from_orm(svc.get_me(db, user.id))


@router.patch("/me", response_model=MeOut, summary="Update own profile")
def patch_me(
    body: MePatchIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeOut:
    return MeOut.from_orm(
        svc.patch_me(
            db,
            user.id,
            full_name=body.full_name,
            email=body.email,
            city=body.city,
        )
    )


@router.post(
    "/me/avatar",
    response_model=MeOut,
    summary="Set avatar (URL stub — multipart upload arrives in Phase 4)",
)
def set_avatar(
    body: AvatarIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeOut:
    return MeOut.from_orm(svc.set_avatar(db, user.id, avatar_url=body.avatar_url))
