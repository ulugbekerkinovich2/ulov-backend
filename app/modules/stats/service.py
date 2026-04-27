"""Owner dashboard analytics — read-only aggregations.

Phase 6 pre-aggregates over the live ``services`` + ``service_items`` tables.
At higher centre volumes a materialised view + nightly refresh would replace
these queries; for now the queue and history fit easily in a single
center-scoped scan.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.deps import CurrentUser
from app.modules.service_centers import service as centers_svc
from app.modules.services.models import Service, ServiceItem

UUIDLike = Union[UUID, str]


def _utc_today() -> date:
    return datetime.now(tz=timezone.utc).date()


# ---------------------------------------------------------------------------
# Overview — single-centre KPIs
# ---------------------------------------------------------------------------
def overview(db: Session, center_id: UUIDLike, user: CurrentUser) -> Dict[str, Any]:
    centers_svc.assert_ops_access(db, center_id, user)

    rows = db.execute(
        select(Service.status, func.count())
        .where(Service.center_id == center_id)
        .where(Service.deleted_at.is_(None))
        .group_by(Service.status)
    ).all()
    by_status: Dict[str, int] = {status: 0 for status in (
        "waiting", "in_progress", "paused", "completed", "cancelled"
    )}
    for status, count in rows:
        by_status[str(status)] = int(count)

    today_start = datetime.combine(_utc_today(), datetime.min.time(), tzinfo=timezone.utc)
    today_intakes = int(
        db.execute(
            select(func.count())
            .select_from(Service)
            .where(Service.center_id == center_id)
            .where(Service.deleted_at.is_(None))
            .where(Service.created_at >= today_start)
        ).scalar_one()
    )

    return {
        "center_id": str(center_id),
        "by_status": by_status,
        "queue": by_status["waiting"] + by_status["in_progress"] + by_status["paused"],
        "today_intakes": today_intakes,
    }


# ---------------------------------------------------------------------------
# Revenue — sum of completed services' (service_price + parts_price)
# ---------------------------------------------------------------------------
def revenue(
    db: Session,
    center_id: UUIDLike,
    user: CurrentUser,
    *,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    centers_svc.assert_ops_access(db, center_id, user)

    start = datetime.combine(
        date_from or (_utc_today() - timedelta(days=30)),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    end = datetime.combine(
        date_to or _utc_today(),
        datetime.max.time(),
        tzinfo=timezone.utc,
    )

    # Total revenue across the window.
    total = db.execute(
        select(
            func.coalesce(
                func.sum(ServiceItem.service_price + ServiceItem.parts_price), 0
            )
        )
        .select_from(ServiceItem)
        .join(Service, Service.id == ServiceItem.service_id)
        .where(Service.center_id == center_id)
        .where(Service.status == "completed")
        .where(Service.completed_at >= start)
        .where(Service.completed_at <= end)
    ).scalar_one()

    # Per-day breakdown for charting.
    day_col = func.date_trunc("day", Service.completed_at).label("day")
    daily = db.execute(
        select(
            day_col,
            func.coalesce(
                func.sum(ServiceItem.service_price + ServiceItem.parts_price), 0
            ).label("amount"),
            func.count(func.distinct(Service.id)).label("services"),
        )
        .select_from(ServiceItem)
        .join(Service, Service.id == ServiceItem.service_id)
        .where(Service.center_id == center_id)
        .where(Service.status == "completed")
        .where(Service.completed_at >= start)
        .where(Service.completed_at <= end)
        .group_by(day_col)
        .order_by(day_col)
    ).all()

    # Top Services
    top_services = db.execute(
        select(ServiceItem.service_type, func.count(ServiceItem.id).label("count"))
        .join(Service, Service.id == ServiceItem.service_id)
        .where(Service.center_id == center_id)
        .where(Service.status == "completed")
        .where(Service.completed_at >= start)
        .where(Service.completed_at <= end)
        .group_by(ServiceItem.service_type)
        .order_by(text("count DESC"))
        .limit(10)
    ).all()

    # Top Brands
    from app.modules.cars.models import Car
    top_brands = db.execute(
        select(Car.brand, func.count(Service.id).label("count"))
        .join(Service, Service.car_id == Car.id)
        .where(Service.center_id == center_id)
        .where(Service.status == "completed")
        .where(Service.completed_at >= start)
        .where(Service.completed_at <= end)
        .group_by(Car.brand)
        .order_by(text("count DESC"))
        .limit(10)
    ).all()

    return {
        "center_id": str(center_id),
        "from": start.date().isoformat(),
        "to": end.date().isoformat(),
        "total": int(total or 0),
        "daily": [
            {
                "day": row.day.date().isoformat() if row.day else None,
                "amount": int(row.amount or 0),
                "services": int(row.services or 0),
            }
            for row in daily
        ],
        "top_services": [
            {"name": row.service_type, "count": int(row.count)}
            for row in top_services
        ],
        "top_brands": [
            {"name": row.brand, "count": int(row.count)}
            for row in top_brands
        ]
    }


# ---------------------------------------------------------------------------
# Mechanic load — completed-services count + revenue per mechanic
# ---------------------------------------------------------------------------
def mechanic_load(
    db: Session, center_id: UUIDLike, user: CurrentUser
) -> List[Dict[str, Any]]:
    centers_svc.assert_ops_access(db, center_id, user)

    rows = db.execute(
        select(
            Service.mechanic_id,
            func.count(Service.id).label("services"),
            func.coalesce(
                func.sum(ServiceItem.service_price + ServiceItem.parts_price), 0
            ).label("revenue"),
        )
        .select_from(Service)
        .join(ServiceItem, ServiceItem.service_id == Service.id, isouter=True)
        .where(Service.center_id == center_id)
        .where(Service.deleted_at.is_(None))
        .group_by(Service.mechanic_id)
    ).all()

    return [
        {
            "mechanic_id": str(row.mechanic_id) if row.mechanic_id else None,
            "services": int(row.services or 0),
            "revenue": int(row.revenue or 0),
        }
        for row in rows
    ]
