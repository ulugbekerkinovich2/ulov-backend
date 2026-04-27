"""Content DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class ContentPageOut(BaseModel):
    id: UUID
    kind: str
    lang: str
    slug: str
    title: str
    body: Dict[str, Any]
    updated_at: datetime

    class Config:
        orm_mode = True


class ContentListOut(BaseModel):
    kind: str
    lang: str
    items: List[ContentPageOut]

class StoryIn(BaseModel):
    title: str
    image_url: str
    content: Optional[str] = None
    discount_label: Optional[str] = None
    valid_until: Optional[datetime] = None

class StoryOut(BaseModel):
    id: UUID
    center_id: Optional[UUID]
    title: str
    image_url: str
    content: Optional[str]
    discount_label: Optional[str]
    valid_until: Optional[datetime]
    created_at: datetime

    class Config:
        orm_mode = True
