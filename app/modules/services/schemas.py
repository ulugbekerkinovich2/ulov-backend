"""Service DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator

from app.modules.services.models import (
    CONDITION_IMAGE_STAGE_VALUES,
    SERVICE_STATUS_VALUES,
)


class ServiceOwnerOut(BaseModel):
    id: UUID
    full_name: Optional[str]
    phone: str

    class Config:
        orm_mode = True


class ServiceCarOut(BaseModel):
    id: UUID
    brand: str
    model: str
    year: int
    plate: str
    color: Optional[str] = None
    vin: Optional[str] = None
    mileage: int
    owner: Optional[ServiceOwnerOut] = None

    class Config:
        orm_mode = True


class ServiceItemIn(BaseModel):
    service_type: str = Field(..., min_length=1, max_length=64)
    parts: List[Dict[str, Any]] = Field(default_factory=list)
    notes: Optional[str] = None
    service_price: int = Field(0, ge=0)
    parts_price: int = Field(0, ge=0)


class ServiceItemOut(ServiceItemIn):
    id: UUID
    service_id: UUID
    created_at: datetime

    class Config:
        orm_mode = True


class ServiceCreateIn(BaseModel):
    car_id: UUID
    mechanic_id: Optional[UUID] = None
    mileage_at_intake: int = Field(..., ge=0, le=10_000_000)
    next_recommended_mileage: Optional[int] = Field(None, ge=0, le=10_000_000)
    notes: Optional[str] = None
    items: List[ServiceItemIn] = Field(default_factory=list)


class IntakeIn(BaseModel):
    """Convenience intake — VIN or plate + mileage to open a service."""

    vin: Optional[str] = Field(None, min_length=17, max_length=17)
    plate: Optional[str] = Field(None, min_length=1, max_length=20)
    mileage_at_intake: int = Field(..., ge=0, le=10_000_000)
    mechanic_id: Optional[UUID] = None
    notes: Optional[str] = None


class ServicePatchIn(BaseModel):
    mechanic_id: Optional[UUID] = None
    next_recommended_mileage: Optional[int] = Field(None, ge=0, le=10_000_000)
    notes: Optional[str] = None
    items: Optional[List[ServiceItemIn]] = None


class TransitionIn(BaseModel):
    to_status: str = Field(..., regex="^(in_progress|paused|completed|cancelled)$")
    reason: Optional[str] = Field(None, max_length=500)


class ConditionPhotoIn(BaseModel):
    """Either a fully-formed ``url`` or an upload ``key`` from
    ``POST /uploads/presign``. The latter is the recommended path: the server
    resolves it to a public URL using ``S3_PUBLIC_URL`` so the client never
    has to know how the bucket is exposed."""

    url: Optional[str] = Field(None, min_length=1, max_length=500)
    key: Optional[str] = Field(None, min_length=1, max_length=512)
    stage: str = Field(..., regex="^(before|during|after)$")

    @validator("key", always=True)
    def _require_one(cls, v, values):  # noqa: N805
        if not v and not values.get("url"):
            raise ValueError("either url or key is required")
        return v


class ConditionPhotoOut(BaseModel):
    id: UUID
    service_id: UUID
    url: str
    stage: str
    uploaded_by: Optional[UUID]
    at: datetime

    class Config:
        orm_mode = True


class TransitionOut(BaseModel):
    id: UUID
    service_id: UUID
    from_status: Optional[str]
    to_status: str
    by_user_id: Optional[UUID]
    reason: Optional[str]
    at: datetime

    class Config:
        orm_mode = True


class ServiceOut(BaseModel):
    id: UUID
    car_id: UUID
    center_id: UUID
    mechanic_id: Optional[UUID]
    status: str
    mileage_at_intake: int
    next_recommended_mileage: Optional[int]
    notes: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    paused_at: Optional[datetime]
    paused_elapsed_s: int
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancel_reason: Optional[str]
    pause_reason: Optional[str]
    items: List[ServiceItemOut] = Field(default_factory=list)
    car: Optional[ServiceCarOut] = None
    center_name: Optional[str] = None
    mechanic_name: Optional[str] = None

    class Config:
        orm_mode = True


class CarLookupOut(BaseModel):
    car_id: UUID
    owner_id: UUID
    brand: str
    model: str
    year: int
    plate: str
    vin: Optional[str]
    mileage: int

    class Config:
        orm_mode = True


# Re-export raw value tuples so callers don't reimport models.
ALL_STATES = tuple(SERVICE_STATUS_VALUES)
ALL_PHOTO_STAGES = tuple(CONDITION_IMAGE_STAGE_VALUES)
