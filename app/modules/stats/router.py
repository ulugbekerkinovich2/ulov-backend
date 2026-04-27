"""Stats endpoints — owner dashboard read-only KPIs."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_staff, get_db
from app.modules.stats import service as svc

router = APIRouter()


@router.get(
    "/service-centers/{center_id}/stats/overview",
    response_model=Dict[str, Any],
    summary="Centre KPI snapshot — queue size, today's intakes, by-status counts",
)
def overview(
    center_id: UUID,
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return svc.overview(db, center_id, user)


@router.get(
    "/service-centers/{center_id}/stats/revenue",
    response_model=Dict[str, Any],
    summary="Revenue total + per-day breakdown for completed services",
)
def revenue(
    center_id: UUID,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return svc.revenue(
        db, center_id, user, date_from=date_from, date_to=date_to
    )


@router.get(
    "/service-centers/{center_id}/stats/mechanics",
    response_model=List[Dict[str, Any]],
    summary="Per-mechanic completed-service count + revenue",
)
def mechanic_load(
    center_id: UUID,
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    return svc.mechanic_load(db, center_id, user)
