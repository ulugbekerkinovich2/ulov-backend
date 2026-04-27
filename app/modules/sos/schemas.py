"""SOS DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SosProviderOut(BaseModel):
    id: UUID
    category: str
    name: str
    phone: str
    city: Optional[str]
    available_24_7: bool

    class Config:
        orm_mode = True


class SosRequestIn(BaseModel):
    provider_id: Optional[UUID] = None
    category: Optional[str] = Field(None, regex="^(tow|roadside|fuel|ambulance|police)$")
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    note: Optional[str] = Field(None, max_length=500)


class SosRequestOut(BaseModel):
    id: UUID
    user_id: UUID
    provider_id: Optional[UUID]
    status: str
    lat: Optional[float]
    lng: Optional[float]
    note: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True
