"""Insurance DTOs."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CompanyOut(BaseModel):
    id: UUID
    name: str
    rating: float
    reviews_count: int
    logo_url: Optional[str]
    base_price: int
    perks: list
    active: bool

    class Config:
        orm_mode = True


class BuyPolisIn(BaseModel):
    car_id: UUID
    company_id: UUID
    applicant_name: str
    passport_series: str
    passport_number: str
    birth_date: date
    phone: str
    period_months: int
    payment_method: str


class TariffOut(BaseModel):
    id: UUID
    code: str
    name: str
    base_price: int
    coefficients: Dict[str, Any]
    active: bool

    class Config:
        orm_mode = True


class QuoteIn(BaseModel):
    tariff_code: str = Field(..., min_length=1, max_length=64)
    car_id: UUID


class QuoteOut(BaseModel):
    tariff_code: str
    car_id: UUID
    price: int  # tiyin
    breakdown: Dict[str, Any]


class PolicyCreateIn(BaseModel):
    tariff_code: str = Field(..., min_length=1, max_length=64)
    car_id: UUID
    valid_from: date
    valid_to: date


class PolicyOut(BaseModel):
    id: UUID
    user_id: UUID
    car_id: UUID
    company_id: Optional[UUID]
    price: int
    valid_from: date = Field(..., alias="start_date")
    valid_to: date = Field(..., alias="end_date")
    payment_status: str = Field(..., alias="status")
    external_ref: Optional[str] = Field(None, alias="polis_number")
    created_at: datetime

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
