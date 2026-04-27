"""SOS endpoints — provider directory + request log."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.deps import CurrentUser, get_current_customer, get_db
from app.modules.sos.models import SosProvider, SosRequest
from app.modules.sos.schemas import (
    SosProviderOut,
    SosRequestIn,
    SosRequestOut,
)

log = get_logger(__name__)
router = APIRouter()


@router.get(
    "/providers",
    response_model=List[SosProviderOut],
    summary="List SOS providers (filterable by category and city)",
)
def list_providers(
    category: Optional[str] = Query(
        None, regex="^(tow|roadside|fuel|ambulance|police)$"
    ),
    city: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
) -> List[SosProviderOut]:
    stmt = select(SosProvider).order_by(SosProvider.created_at.desc())
    if category:
        stmt = stmt.where(SosProvider.category == category)
    if city:
        stmt = stmt.where(SosProvider.city == city)
    return [SosProviderOut.from_orm(p) for p in db.execute(stmt).scalars()]


@router.post(
    "/requests",
    response_model=SosRequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Log an SOS request — fire-and-log audit trail",
)
def create_request(
    body: SosRequestIn,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> SosRequestOut:
    if body.provider_id is None and body.category is None:
        raise ValidationError(
            "provider_id or category required",
            code="SOS_PROVIDER_OR_CATEGORY_REQUIRED",
        )

    provider = None
    if body.provider_id is not None:
        provider = db.execute(
            select(SosProvider).where(SosProvider.id == body.provider_id)
        ).scalar_one_or_none()
        if provider is None:
            raise NotFoundError("Provider not found", code="SOS_PROVIDER_NOT_FOUND")

    req = SosRequest(
        user_id=user.id,
        provider_id=provider.id if provider else None,
        lat=body.lat,
        lng=body.lng,
        note=body.note,
    )
    db.add(req)
    db.flush()
    log.info(
        "sos_request_created",
        sos_id=str(req.id),
        user_id=str(user.id),
        category=body.category,
    )
    return SosRequestOut.from_orm(req)
