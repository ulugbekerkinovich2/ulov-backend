"""Fuel station search — geo-filtered list with optional fuel-type filter.

The ``location`` column is JSONB ``{lat, lng}``; we do a haversine filter in
Python rather than rely on PostGIS so the local dev stack stays portable.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.modules.fuel_stations.models import FuelStation

router = APIRouter()


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371008.8  # Earth radius in metres.
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _to_dict(station: FuelStation, distance_m: float) -> Dict[str, Any]:
    loc = station.location if isinstance(station.location, dict) else None
    return {
        "id": str(station.id),
        "name": station.name,
        "brand": station.brand,
        "address": station.address,
        "location": loc,
        "prices": station.prices or {},
        "distance_m": round(distance_m, 2),
    }


@router.get(
    "/prices/current",
    summary="Median current price per fuel type across all stations",
)
def current_prices(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Aggregate current fuel prices across every station with a price set.

    Used by the user app's home-screen widget — the per-station detail still
    comes from ``GET /fuel-stations``. We return medians (not means) so a
    single mis-typed entry can't skew the headline number.
    """
    rows = db.execute(select(FuelStation)).scalars().all()
    buckets: Dict[str, List[float]] = {}
    for s in rows:
        prices = s.prices or {}
        for code, raw in prices.items():
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue
            buckets.setdefault(code, []).append(value)

    items: List[Dict[str, Any]] = []
    for code, values in buckets.items():
        values.sort()
        n = len(values)
        median = (
            (values[n // 2 - 1] + values[n // 2]) / 2
            if n % 2 == 0
            else values[n // 2]
        )
        items.append({
            "code": code,
            "price": round(median, 2),
            "samples": n,
            # Historical delta requires a price-history table we don't keep
            # yet. Emit zero so the UI can show a neutral indicator.
            "delta": 0.0,
        })
    items.sort(key=lambda x: x["code"])
    return {"items": items}


@router.get(
    "",
    response_model=List[Dict[str, Any]],
    summary="Find fuel stations within a radius (optionally filtered by fuel type)",
)
def list_nearby(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(5000, ge=100, le=200_000),
    fuel: Optional[str] = Query(None, max_length=32),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    rows = db.execute(select(FuelStation)).scalars().all()
    out: List[tuple] = []
    for s in rows:
        loc = s.location if isinstance(s.location, dict) else None
        if loc is None or "lat" not in loc or "lng" not in loc:
            continue
        d = _haversine_m(lat, lng, float(loc["lat"]), float(loc["lng"]))
        if d > radius_m:
            continue
        if fuel:
            prices = s.prices or {}
            if fuel not in prices:
                continue
        out.append((s, d))
    out.sort(key=lambda r: r[1])
    return [_to_dict(s, d) for s, d in out[:limit]]
