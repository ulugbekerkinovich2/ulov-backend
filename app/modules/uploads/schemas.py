"""Upload DTOs."""

from __future__ import annotations

from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator

# Allow-listed media content types — anything else gets a 400.
# Stories accept short-form videos as well as photos; everything else is
# image-only and the service-layer guard tightens that further.
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "video/mp4",
    "video/quicktime",
    "video/webm",
}

UPLOAD_KINDS = {
    "avatar",
    "car_photo",
    "center_avatar",
    "center_gallery",
    "service_photo",
    "story_image",
}


class PresignIn(BaseModel):
    kind: str = Field(..., description="One of: avatar, car_photo, center_avatar, center_gallery, service_photo")
    content_type: str = Field(..., min_length=3, max_length=64)
    size_bytes: int = Field(..., ge=1)
    # Owner-supplied filename — used only to pick the extension.
    filename: Optional[str] = Field(None, max_length=255)
    # Optional scoping — ties the upload to a specific entity (car, service…).
    entity_id: Optional[UUID] = None

    @validator("kind")
    def _check_kind(cls, v: str) -> str:  # noqa: N805
        if v not in UPLOAD_KINDS:
            raise ValueError(f"unsupported kind: {v}")
        return v

    @validator("content_type")
    def _check_ct(cls, v: str) -> str:  # noqa: N805
        v = v.lower().strip()
        if v not in ALLOWED_CONTENT_TYPES:
            raise ValueError(f"content_type {v} not allowed")
        return v


class PresignOut(BaseModel):
    """Server returns a presigned PUT URL the client uploads to directly.

    After upload, the client confirms with ``POST /uploads/confirm`` so the
    backend can record the final object URL on the relevant entity.
    """

    upload_url: str
    method: str = "PUT"
    headers: Dict[str, str]
    key: str
    public_url: str
    expires_in: int


class ConfirmIn(BaseModel):
    kind: str
    key: str = Field(..., min_length=1, max_length=512)
    entity_id: Optional[UUID] = None

    @validator("kind")
    def _check_kind(cls, v: str) -> str:  # noqa: N805
        if v not in UPLOAD_KINDS:
            raise ValueError(f"unsupported kind: {v}")
        return v


class ConfirmOut(BaseModel):
    kind: str
    public_url: str
    entity_id: Optional[UUID]
