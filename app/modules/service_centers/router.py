"""Service centre endpoints."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_owner, get_current_user, get_db
from app.modules.service_centers import service as svc
from app.modules.service_centers.schemas import (
    LatLng,
    ServiceCenterCreateIn,
    ServiceCenterOut,
    ServiceCenterPatchIn,
)

router = APIRouter()


def _to_out(center) -> ServiceCenterOut:
    return ServiceCenterOut(
        id=center.id,
        owner_user_id=center.owner_user_id,
        name=center.name,
        phone=center.phone,
        address=center.address,
        description=center.description,
        location=svc.location_to_dict(center),
        schedule=center.schedule or {},
        services=list(center.services or []),
        avatar_url=center.avatar_url,
        subscription_plan_id=center.subscription_plan_id,
        subscription_until=center.subscription_until,
        created_at=center.created_at,
        updated_at=center.updated_at,
    )


@router.get("", response_model=List[ServiceCenterOut], summary="List my service centres")
def list_my_centers(
    user: CurrentUser = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> List[ServiceCenterOut]:
    return [_to_out(c) for c in svc.list_mine(db, user)]


@router.post(
    "",
    response_model=ServiceCenterOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service centre",
)
def create_center(
    body: ServiceCenterCreateIn,
    user: CurrentUser = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> ServiceCenterOut:
    return _to_out(svc.create(db, user, body.dict()))


@router.get(
    "/nearby",
    response_model=List[dict],
    summary="Find centres within a radius (any authenticated user)",
)
def nearby(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(5000, ge=100, le=100_000),
    limit: int = Query(20, ge=1, le=100),
    _user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[dict]:
    out: List[dict] = []
    for center, distance in svc.nearby(db, lat=lat, lng=lng, radius_m=radius_m, limit=limit):
        out.append({
            **_to_out(center).dict(),
            "distance_m": round(distance, 2),
        })
    return out


@router.get("/{center_id}", response_model=ServiceCenterOut, summary="Get one centre")
def get_center(
    center_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ServiceCenterOut:
    return _to_out(svc.get_or_404(db, center_id))


@router.patch("/{center_id}", response_model=ServiceCenterOut, summary="Update centre fields")
def patch_center(
    center_id: UUID,
    body: ServiceCenterPatchIn,
    user: CurrentUser = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> ServiceCenterOut:
    return _to_out(svc.patch(db, center_id, user, body.dict(exclude_unset=True)))


@router.delete(
    "/{center_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a centre",
    response_model=None,
)
def delete_center(
    center_id: UUID,
    user: CurrentUser = Depends(get_current_owner),
    db: Session = Depends(get_db),
):
    svc.delete(db, center_id, user)
