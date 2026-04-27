"""Trip DTOs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TripStartIn(BaseModel):
    car_id: Optional[UUID] = None


class TripPointIn(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    speed: Optional[float] = Field(None, ge=0, le=500)
    heading: Optional[float] = Field(None, ge=0, le=360)
    ts: Optional[datetime] = None


class TripPointsBatchIn(BaseModel):
    points: List[TripPointIn] = Field(..., min_items=1, max_items=500)


class TripOut(BaseModel):
    id: UUID
    user_id: UUID
    car_id: Optional[UUID]
    started_at: datetime
    finished_at: Optional[datetime]
    distance_km: Decimal
    duration_s: int
    avg_speed: Decimal
    fuel_l_est: Decimal
    polyline: Optional[str]

    class Config:
        orm_mode = True
