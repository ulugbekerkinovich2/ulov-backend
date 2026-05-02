"""Cars DTOs. Plate/VIN/tech-passport normalisation happens here."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator

from app.core.plate import (
    PlateType,
    detect_plate_type,
    normalize_plate,
    validate_plate_type,
    validate_tech_passport,
    validate_vin,
)


# ---------------------------------------------------------------------------
# Shared validators — reusable across In shapes
# ---------------------------------------------------------------------------
def _norm_plate_with_type(v: str, values: dict) -> str:
    # If the client explicitly supplied ``plate_type``, enforce it; otherwise
    # detect automatically.
    pt = values.get("plate_type")
    if pt:
        try:
            return validate_plate_type(v, PlateType(pt))
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
    try:
        return normalize_plate(v)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def _norm_vin(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    try:
        return validate_vin(v)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def _norm_tech_passport(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    try:
        return validate_tech_passport(v)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
class CarCreateIn(BaseModel):
    brand: str = Field(..., min_length=1, max_length=64)
    model: str = Field(..., min_length=1, max_length=64)
    year: int = Field(..., ge=1950, le=2100)
    color: Optional[str] = Field(None, max_length=32)

    plate: str = Field(..., min_length=1, max_length=20)
    plate_type: Optional[PlateType] = None  # auto-detected when missing

    mileage: int = Field(0, ge=0, le=10_000_000)

    vin: Optional[str] = None
    tech_passport: Optional[str] = None

    insurance_from: Optional[date] = None
    insurance_to: Optional[date] = None
    insurance_company: Optional[str] = Field(None, max_length=100)
    tint_from: Optional[date] = None
    tint_to: Optional[date] = None

    photo_url: Optional[str] = Field(None, max_length=500)


class WalkinCarIn(CarCreateIn):
    """Staff-side payload for registering a walk-in customer's car.

    Re-uses ``CarCreateIn``'s validation for the vehicle fields and adds the
    owner's phone (mandatory; we look the customer up by phone, creating a
    placeholder account if none exists) and an optional display name.
    """

    owner_phone: str = Field(..., min_length=4, max_length=20)
    owner_name: Optional[str] = Field(None, max_length=255)

    @validator("owner_phone")
    def _norm_owner_phone(cls, v: str) -> str:  # noqa: N805
        from app.core.phone import normalize_phone

        return normalize_phone(v)

    def car_payload(self) -> dict:
        """Strip the owner-only fields so the result fits ``CarCreateIn``."""
        data = self.dict(exclude_unset=False)
        data.pop("owner_phone", None)
        data.pop("owner_name", None)
        return data

    @validator("plate")
    def _norm_plate(cls, v: str, values: dict) -> str:  # noqa: N805
        return _norm_plate_with_type(v, values)

    @validator("vin")
    def _norm_vin(cls, v: Optional[str]) -> Optional[str]:  # noqa: N805
        return _norm_vin(v)

    @validator("tech_passport")
    def _norm_tp(cls, v: Optional[str]) -> Optional[str]:  # noqa: N805
        return _norm_tech_passport(v)

    @validator("insurance_to", always=True)
    def _ins_order(cls, v: Optional[date], values: dict) -> Optional[date]:  # noqa: N805
        start = values.get("insurance_from")
        if v is not None and start is not None and v < start:
            raise ValueError("insurance_to must be on or after insurance_from")
        return v

    @validator("tint_to", always=True)
    def _tint_order(cls, v: Optional[date], values: dict) -> Optional[date]:  # noqa: N805
        start = values.get("tint_from")
        if v is not None and start is not None and v < start:
            raise ValueError("tint_to must be on or after tint_from")
        return v


class CarPatchIn(BaseModel):
    brand: Optional[str] = Field(None, min_length=1, max_length=64)
    model: Optional[str] = Field(None, min_length=1, max_length=64)
    year: Optional[int] = Field(None, ge=1950, le=2100)
    color: Optional[str] = Field(None, max_length=32)

    plate: Optional[str] = Field(None, min_length=1, max_length=20)
    plate_type: Optional[PlateType] = None

    mileage: Optional[int] = Field(None, ge=0, le=10_000_000)

    vin: Optional[str] = None
    tech_passport: Optional[str] = None

    insurance_from: Optional[date] = None
    insurance_to: Optional[date] = None
    insurance_company: Optional[str] = Field(None, max_length=100)
    tint_from: Optional[date] = None
    tint_to: Optional[date] = None

    photo_url: Optional[str] = Field(None, max_length=500)

    @validator("plate")
    def _norm_plate(cls, v: Optional[str], values: dict) -> Optional[str]:  # noqa: N805
        if v is None:
            return None
        return _norm_plate_with_type(v, values)

    @validator("vin")
    def _norm_vin(cls, v: Optional[str]) -> Optional[str]:  # noqa: N805
        return _norm_vin(v)

    @validator("tech_passport")
    def _norm_tp(cls, v: Optional[str]) -> Optional[str]:  # noqa: N805
        return _norm_tech_passport(v)


class MileageReadingIn(BaseModel):
    value: int = Field(..., ge=0, le=10_000_000)


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
class CarOut(BaseModel):
    id: UUID
    owner_id: UUID
    brand: str
    model: str
    year: int
    color: Optional[str]
    plate: str
    plate_type: str
    mileage: int
    vin: Optional[str]
    tech_passport: Optional[str]
    insurance_from: Optional[date]
    insurance_to: Optional[date]
    insurance_company: Optional[str]
    tint_from: Optional[date]
    tint_to: Optional[date]
    photo_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class RecommendationItem(BaseModel):
    service_type: str
    reason: str
    priority: str  # "due" | "upcoming" | "optional"
    interval_km: Optional[int] = None
    next_due_km: Optional[int] = None


class RecommendationsOut(BaseModel):
    car_id: UUID
    mileage: int
    items: List[RecommendationItem]
