"""Billing DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PlanOut(BaseModel):
    id: UUID
    code: str
    name: str
    monthly_price: int
    duration_days: int
    active: bool

    class Config:
        orm_mode = True


class CheckoutIn(BaseModel):
    plan_code: str = Field(..., min_length=1, max_length=64)
    center_id: UUID
    provider: str = Field(..., regex="^(payme|click|stripe|manual)$")


class CheckoutOut(BaseModel):
    payment_id: UUID
    amount: int
    provider: str
    status: str
    # The frontend follows ``redirect_url`` to the provider's checkout. For
    # Payme/Click in this stub we hand back a placeholder; Phase 7 wires real
    # SDKs.
    redirect_url: str


class WebhookIn(BaseModel):
    """Provider-agnostic webhook envelope.

    Real Payme/Click bodies are very different; we'll add a thin adapter for
    each in Phase 7. For now this shape is what the manual / Stripe stub
    posts.
    """

    payment_id: UUID
    external_ref: str = Field(..., min_length=1, max_length=255)
    status: str = Field(..., regex="^(paid|failed)$")


class PaymentOut(BaseModel):
    id: UUID
    user_id: UUID
    kind: str
    target_id: Optional[UUID]
    plan_id: Optional[UUID]
    amount: int
    provider: str
    status: str
    external_ref: Optional[str]
    created_at: datetime
    paid_at: Optional[datetime]

    class Config:
        orm_mode = True
