"""Users module DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class MeOut(BaseModel):
    id: UUID
    phone: str
    full_name: Optional[str]
    email: Optional[str]
    city: Optional[str]
    avatar_url: Optional[str]
    role: str
    center_id: Optional[UUID]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class MePatchIn(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    city: Optional[str] = Field(None, max_length=100)


class AvatarIn(BaseModel):
    """P2 stub body — accepts a URL the client has already uploaded somewhere.

    Phase 4 replaces this with a multipart upload → S3 presigned flow; the
    response shape (``MeOut``) does not change.
    """

    avatar_url: Optional[str] = Field(None, max_length=500)
