"""Auth domain logic.

All business rules — OTP lifecycle, registration, login, refresh rotation,
password reset — live here. Routers are thin translation layers; repositories
are thin SQL layers. Nothing else understands the auth rules.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple, Union
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.modules.auth import repository as repo
from app.modules.mechanics import repository as mech_repo
from app.modules.service_centers import repository as center_repo
from app.modules.users.models import User

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


# ---------------------------------------------------------------------------
# OTP — Redis only. No DB rows.
# ---------------------------------------------------------------------------
def _otp_key(phone: str) -> str:
    return f"otp:{phone}"


def _otp_lock_key(phone: str) -> str:
    return f"otp:lock:{phone}"


async def request_otp(redis: Redis, phone: str) -> Tuple[str, int]:
    """Generate + persist a one-time password. Returns ``(code, ttl_seconds)``.

    Honours the phone-level lock that ``verify_otp`` installs after too many
    failed attempts.
    """
    if await redis.exists(_otp_lock_key(phone)):
        raise UnauthorizedError(
            "Too many attempts, try later", code="AUTH_OTP_LOCKED"
        )

    code = f"{secrets.randbelow(1_000_000):06d}"
    ttl = settings.OTP_TTL_SECONDS
    key = _otp_key(phone)
    await redis.delete(key)  # clear any prior unverified OTP
    await redis.hset(key, mapping={"code": code, "attempts": "0"})
    await redis.expire(key, ttl)
    log.info("otp_issued", phone=phone, ttl=ttl)
    return code, ttl


async def verify_otp(redis: Redis, phone: str, code: str) -> None:
    """Consume an OTP. Raises on mismatch/expiry.

    After :data:`settings.OTP_MAX_ATTEMPTS` wrong tries the phone is locked
    for :data:`settings.OTP_LOCK_SECONDS`.
    """
    key = _otp_key(phone)
    stored = await redis.hgetall(key)
    if not stored:
        raise UnauthorizedError(
            "OTP expired or not requested", code="AUTH_OTP_EXPIRED"
        )

    if stored.get("code") != code:
        attempts = await redis.hincrby(key, "attempts", 1)
        if attempts >= settings.OTP_MAX_ATTEMPTS:
            await redis.delete(key)
            await redis.setex(
                _otp_lock_key(phone), settings.OTP_LOCK_SECONDS, "1"
            )
            raise UnauthorizedError(
                "Too many attempts, try later", code="AUTH_OTP_LOCKED"
            )
        raise UnauthorizedError("Invalid OTP", code="AUTH_OTP_INVALID")

    # Success — consume immediately so it can't be reused.
    await redis.delete(key)
    log.info("otp_verified", phone=phone)


# ---------------------------------------------------------------------------
# Registration / login
# ---------------------------------------------------------------------------
def register(
    db: Session,
    *,
    phone: str,
    password: str,
    full_name: Optional[str] = None,
    email: Optional[str] = None,
    city: Optional[str] = None,
) -> User:
    if repo.get_user_by_phone(db, phone) is not None:
        raise ConflictError("Phone already registered", code="AUTH_PHONE_TAKEN")
    user = repo.create_user(
        db,
        phone=phone,
        password_hash=hash_password(password),
        full_name=full_name,
        email=email,
        city=city,
        role="customer",
    )
    log.info("user_registered", user_id=str(user.id), phone=phone)
    return user


def authenticate(db: Session, *, phone: str, password: str) -> User:
    user = repo.get_user_by_phone(db, phone)
    # Constant-time-ish: always call verify_password so a missing user costs
    # approximately the same wall-time as a wrong password.
    dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"  # noqa: S105
    if user is None:
        verify_password(password, dummy_hash)
        raise UnauthorizedError(
            "Invalid credentials", code="AUTH_INVALID_CREDENTIALS"
        )
    if not verify_password(password, user.password_hash):
        raise UnauthorizedError(
            "Invalid credentials", code="AUTH_INVALID_CREDENTIALS"
        )
    if not user.is_active:
        raise UnauthorizedError("Account disabled", code="AUTH_DISABLED")
    return user


def register_center(
    db: Session,
    *,
    phone: str,
    password: str,
    full_name: str,
    center_name: str,
    center_phone: str,
    center_address: str,
    center_services: Optional[List[str]] = None,
) -> Tuple[User, Any]:
    if repo.get_user_by_phone(db, phone) is not None:
        raise ConflictError("Phone already registered", code="AUTH_PHONE_TAKEN")

    # 1. Create the owner user
    user = repo.create_user(
        db,
        phone=phone,
        password_hash=hash_password(password),
        full_name=full_name,
        role="owner",
    )

    # 2. Create the centre
    center = center_repo.create(
        db,
        owner_user_id=user.id,
        name=center_name,
        phone=center_phone,
        address=center_address,
        services=center_services or [],
    )

    # 3. Update the user with center_id
    db.execute(
        update(User).where(User.id == user.id).values(center_id=center.id)
    )
    db.flush()

    log.info(
        "center_registered",
        user_id=str(user.id),
        center_id=str(center.id),
        phone=phone,
    )
    return user, center


def authenticate_mechanic(db: Session, *, login: str, password: str) -> Any:
    m = mech_repo.get_by_login(db, login)
    dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"  # noqa: S105
    if m is None:
        verify_password(password, dummy_hash)
        raise UnauthorizedError(
            "Invalid credentials", code="AUTH_INVALID_CREDENTIALS"
        )
    if not verify_password(password, m.password_hash):
        raise UnauthorizedError(
            "Invalid credentials", code="AUTH_INVALID_CREDENTIALS"
        )

    # In this architecture, mechanics have their own table. 
    # For now we return the Mechanic object. 
    # To support refresh tokens (which require a users.id FK), 
    # we would need to map them to the users table.
    return m


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
def issue_tokens(
    db: Session,
    *,
    sub: UUIDLike,
    role: str,
    center_id: Optional[UUIDLike] = None,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
) -> Tuple[str, str, int]:
    """Create an access + refresh pair.

    Returns ``(access, raw_refresh, access_ttl_seconds)``.
    """
    access = create_access_token(
        subject=str(sub),
        role=role,
        center_id=str(center_id) if center_id else None,
    )
    raw_refresh = generate_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.JWT_REFRESH_TTL_SECONDS
    )
    
    # Mechanics aren't User rows, so the refresh-tokens FK would fail. We
    # only persist refresh tokens for sub-ids that exist in ``users``; for
    # mechanic logins we still hand back a refresh string so the cookie can
    # be set, but we don't persist server-side state — the access token is
    # what gates the session.
    from app.modules.users.models import User as _User

    user_exists = (
        db.query(_User.id).filter(_User.id == sub).first() is not None
    )
    if user_exists:
        repo.save_refresh(
            db,
            user_id=sub,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=expires_at,
            user_agent=user_agent,
            ip=ip,
        )
    return access, raw_refresh, settings.JWT_ACCESS_TTL_SECONDS


def rotate_refresh(
    db: Session,
    raw_refresh: str,
    *,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
) -> Tuple[str, str, int, User]:
    """Verify, revoke, and issue a fresh pair.

    Returns ``(access, new_refresh, access_ttl, user)``.
    """
    old_hash = hash_refresh_token(raw_refresh)
    token = repo.get_active_refresh(db, old_hash)
    if token is None:
        raise UnauthorizedError(
            "Refresh token invalid or expired", code="AUTH_REFRESH_INVALID"
        )
    user = repo.get_user_by_id(db, token.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Account disabled", code="AUTH_DISABLED")
    repo.revoke_refresh(db, old_hash)
    access, new_refresh, ttl = issue_tokens(
        db,
        sub=user.id,
        role=user.role,
        center_id=user.center_id,
        user_agent=user_agent,
        ip=ip,
    )
    log.info("token_rotated", user_id=str(user.id))
    return access, new_refresh, ttl, user


def logout(db: Session, raw_refresh: Optional[str]) -> None:
    if not raw_refresh:
        return
    repo.revoke_refresh(db, hash_refresh_token(raw_refresh))


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------
def reset_password(db: Session, *, user: User, new_password: str) -> None:
    repo.update_password(db, user.id, password_hash=hash_password(new_password))
    # Nuke all sessions — the user just reset their password, every existing
    # refresh cookie must die.
    revoked = repo.revoke_all_user_refresh(db, user.id)
    log.info("password_reset", user_id=str(user.id), revoked_sessions=revoked)
