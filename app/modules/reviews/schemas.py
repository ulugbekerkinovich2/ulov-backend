"""Reviews DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewCreateIn(BaseModel):
    center_id: UUID
    service_id: Optional[UUID] = None
    rating: int = Field(..., ge=1, le=5)
    text: Optional[str] = Field(None, max_length=2000)


class ReviewOut(BaseModel):
    id: UUID
    user_id: UUID
    center_id: UUID
    service_id: Optional[UUID]
    rating: int
    text: Optional[str]
    reply: Optional[str]
    reply_at: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True
