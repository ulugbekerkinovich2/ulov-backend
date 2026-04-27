"""Auth request/response DTOs (pydantic v1).

All phone inputs are normalised to E.164 at the schema layer, so service and
repository code never sees a free-form phone string.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator

from app.core.phone import normalize_phone


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------
class OtpRequestIn(BaseModel):
    phone: str

    @validator("phone")
    def _norm(cls, v: str) -> str:  # noqa: N805
        return normalize_phone(v)


class OtpRequestOut(BaseModel):
    status: str = "sent"
    ttl_seconds: int
    # Dev-only convenience: return the OTP in the response body so test runners
    # and local devs don't need a real SMS. ``OTP_DEV_ECHO`` must be ``false``
    # in staging/prod.
    dev_code: Optional[str] = None


class OtpVerifyIn(BaseModel):
    phone: str
    code: str = Field(..., min_length=4, max_length=8)

    @validator("phone")
    def _norm(cls, v: str) -> str:  # noqa: N805
        return normalize_phone(v)


# ---------------------------------------------------------------------------
# Register / login
# ---------------------------------------------------------------------------
class RegisterIn(BaseModel):
    phone: str
    password: str = Field(..., min_length=6, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    city: Optional[str] = Field(None, max_length=100)

    @validator("phone")
    def _norm(cls, v: str) -> str:  # noqa: N805
        return normalize_phone(v)


class LoginIn(BaseModel):
    phone: str
    password: str = Field(..., min_length=1, max_length=128)

    @validator("phone")
    def _norm(cls, v: str) -> str:  # noqa: N805
        return normalize_phone(v)


class RegisterCenterIn(BaseModel):
    # User info
    phone: str
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., max_length=255)

    # Centre info
    center_name: str = Field(..., max_length=255)
    center_phone: str = Field(..., max_length=20)
    center_address: str = Field(..., max_length=500)
    center_services: List[str] = Field(default_factory=list)

    @validator("phone", "center_phone")
    def _norm(cls, v: str) -> str:  # noqa: N805
        return normalize_phone(v)


class MechanicLoginIn(BaseModel):
    login: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------
class PasswordResetRequestIn(BaseModel):
    phone: str

    @validator("phone")
    def _norm(cls, v: str) -> str:  # noqa: N805
        return normalize_phone(v)


class PasswordResetConfirmIn(BaseModel):
    phone: str
    code: str = Field(..., min_length=4, max_length=8)
    new_password: str = Field(..., min_length=6, max_length=128)

    @validator("phone")
    def _norm(cls, v: str) -> str:  # noqa: N805
        return normalize_phone(v)


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
class UserOut(BaseModel):
    id: UUID
    phone: str
    full_name: Optional[str]
    email: Optional[str]
    city: Optional[str]
    avatar_url: Optional[str]
    role: str
    center_id: Optional[UUID]
    created_at: datetime

    class Config:
        orm_mode = True


class TokenOut(BaseModel):
    """What goes back on successful login / register / refresh / otp-verify.

    The refresh token is NOT here — it is delivered in an ``httpOnly`` cookie
    so JS code cannot touch it.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires
    user: UserOut
