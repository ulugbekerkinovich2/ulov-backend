"""Low-level security primitives: password hashing + JWT encoding.

This module is deliberately thin — no DB, no Redis. Higher-level auth logic
(refresh rotation, OTP, revocation) lives in ``modules/auth/service.py``.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.config import settings
from app.core.errors import UnauthorizedError

# Argon2id defaults are sensible; tune memory_cost per prod benchmarks.
_hasher = PasswordHasher()


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Return an argon2 hash suitable for storing in the DB."""
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time verify. Returns ``True`` iff the password matches."""
    try:
        _hasher.verify(hashed, password)
        return True
    except VerifyMismatchError:
        return False
    except Exception:  # malformed hash, etc.
        return False


def needs_rehash(hashed: str) -> bool:
    """Whether the stored hash should be upgraded (parameter bump)."""
    return _hasher.check_needs_rehash(hashed)


# ---------------------------------------------------------------------------
# JWT (access tokens only — refresh tokens are opaque, see modules/auth)
# ---------------------------------------------------------------------------
def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(
    *,
    subject: str,
    role: str,
    center_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    ttl_seconds: Optional[int] = None,
) -> str:
    """Encode a short-lived access token.

    Claims:
      sub         — user id (stringified UUID)
      role        — Role enum value
      center_id   — present for mechanic / owner tokens
      iat, exp    — standard
    """
    now = _utcnow()
    ttl = ttl_seconds if ttl_seconds is not None else settings.JWT_ACCESS_TTL_SECONDS
    claims: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    if center_id is not None:
        claims["center_id"] = center_id
    if extra:
        claims.update(extra)
    return jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode + verify. Raises :class:`UnauthorizedError` on any failure."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise UnauthorizedError("Invalid token", code="AUTH_INVALID_TOKEN") from exc
    if "sub" not in payload:
        raise UnauthorizedError("Malformed token", code="AUTH_INVALID_TOKEN")
    return payload


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------
def generate_refresh_token() -> str:
    """256-bit url-safe opaque token."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """SHA-256 of the raw token — used as the Redis / DB key.

    We never store the raw token server-side; a leak of the DB/Redis must not
    let an attacker present a working refresh cookie.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
