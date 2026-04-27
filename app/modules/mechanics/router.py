"""Mechanics endpoints — owner manages roster of one centre."""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_owner, get_current_staff, get_db
from app.modules.mechanics import service as svc
from app.modules.mechanics.schemas import (
    MechanicCreateIn,
    MechanicOut,
    MechanicPatchIn,
)

router = APIRouter()


@router.get(
    "/service-centers/{center_id}/mechanics",
    response_model=List[MechanicOut],
    summary="List mechanics in a centre",
)
def list_mechanics(
    center_id: UUID,
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> List[MechanicOut]:
    return [MechanicOut.from_orm(m) for m in svc.list_for_center(db, center_id, user)]


@router.post(
    "/service-centers/{center_id}/mechanics",
    response_model=MechanicOut,
    status_code=status.HTTP_201_CREATED,
    summary="Hire a new mechanic",
)
def create_mechanic(
    center_id: UUID,
    body: MechanicCreateIn,
    user: CurrentUser = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> MechanicOut:
    return MechanicOut.from_orm(svc.create(db, center_id, user, body.dict()))


@router.patch(
    "/mechanics/{mechanic_id}",
    response_model=MechanicOut,
    summary="Update a mechanic",
)
def patch_mechanic(
    mechanic_id: UUID,
    body: MechanicPatchIn,
    user: CurrentUser = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> MechanicOut:
    return MechanicOut.from_orm(svc.patch(db, mechanic_id, user, body.dict(exclude_unset=True)))


@router.delete(
    "/mechanics/{mechanic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a mechanic",
    response_model=None,
)
def delete_mechanic(
    mechanic_id: UUID,
    user: CurrentUser = Depends(get_current_owner),
    db: Session = Depends(get_db),
):
    svc.delete(db, mechanic_id, user)
