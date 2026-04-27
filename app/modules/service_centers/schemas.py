"""Service centre DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class LatLng(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class ServiceCenterCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=5, max_length=20)
    address: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    location: Optional[LatLng] = None
    schedule: Dict[str, Any] = Field(default_factory=dict)
    services: List[str] = Field(default_factory=list)
    avatar_url: Optional[str] = Field(None, max_length=500)

    @validator("services", each_item=True)
    def _strip_service(cls, v: str) -> str:  # noqa: N805
        v = v.strip()
        if not v:
            raise ValueError("empty service type")
        if len(v) > 64:
            raise ValueError("service type too long")
        return v


class ServiceCenterPatchIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, min_length=5, max_length=20)
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    location: Optional[LatLng] = None
    schedule: Optional[Dict[str, Any]] = None
    services: Optional[List[str]] = None
    avatar_url: Optional[str] = Field(None, max_length=500)


class ServiceCenterOut(BaseModel):
    id: UUID
    owner_user_id: UUID
    name: str
    phone: str
    address: str
    description: Optional[str]
    location: Optional[LatLng]
    schedule: Dict[str, Any]
    services: List[str]
    avatar_url: Optional[str]
    subscription_plan_id: Optional[UUID]
    subscription_until: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class NearbySearchIn(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    radius_m: int = Field(5000, ge=100, le=100_000)
    limit: int = Field(20, ge=1, le=100)
