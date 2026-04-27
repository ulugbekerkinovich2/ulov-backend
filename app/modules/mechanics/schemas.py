"""Mechanic DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class MechanicCreateIn(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    login: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=255)
    service_types: List[str] = Field(default_factory=list)

    @validator("login")
    def _norm_login(cls, v: str) -> str:  # noqa: N805
        v = v.strip().lower()
        if not v.replace("_", "").replace(".", "").replace("-", "").isalnum():
            raise ValueError("login may contain letters, digits, '.', '_' or '-'")
        return v


class MechanicPatchIn(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=6, max_length=255)
    service_types: Optional[List[str]] = None


class MechanicOut(BaseModel):
    id: UUID
    center_id: UUID
    full_name: str
    login: str
    service_types: List[str]
    created_at: datetime

    class Config:
        orm_mode = True
