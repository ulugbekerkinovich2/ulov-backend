"""FastAPI dependencies.

This is the only module allowed to touch both request-scoped state (DB
session, auth) and the global singletons (Redis, S3). Everything else
imports dependencies from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Iterator, Optional

from fastapi import Depends, Header, Request
from redis import asyncio as aioredis
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import UnauthorizedError
from app.core.rbac import Role
from app.core.security import decode_access_token
from app.db.session import SessionLocal


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def get_db() -> Iterator[Session]:
    """Request-scoped SQLAlchemy session.

    Rolls back on exception, always closes on exit.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------
# One async client per logical DB. Created lazily on first access and stored
# on ``app.state`` by ``main.py`` lifespan so tests can replace them wholesale.

async def get_redis(request: Optional[Request] = None, db: int = 0) -> aioredis.Redis:
    """Return an asyncio redis client for logical DB ``db``.

    The connection pool is lifecycle-managed in ``main.py``.
    """
    if request is not None:
        clients = getattr(request.app.state, "redis_clients", None)
        if clients is not None and db in clients:
            return clients[db]
    # Fallback (tests, scripts): build a throw-away client.
    return aioredis.from_url(
        settings.redis_url_for(db), encoding="utf-8", decode_responses=True
    )


async def get_redis_cache(request: Request) -> aioredis.Redis:
    return await get_redis(request, db=settings.REDIS_CACHE_DB)


async def get_redis_otp(request: Request) -> aioredis.Redis:
    return await get_redis(request, db=settings.REDIS_OTP_DB)


async def get_redis_refresh(request: Request) -> aioredis.Redis:
    return await get_redis(request, db=settings.REDIS_REFRESH_DB)


async def get_redis_pubsub(request: Request) -> aioredis.Redis:
    return await get_redis(request, db=settings.REDIS_PUBSUB_DB)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@dataclass
class CurrentUser:
    """A minimal, immutable snapshot of the authenticated user.

    Populated from the JWT alone; no DB round-trip. Routes that need the full
    row should fetch it via the users module.
    """

    id: str
    role: str
    center_id: Optional[str] = None

    @property
    def is_customer(self) -> bool:
        return self.role == Role.CUSTOMER.value

    @property
    def is_staff(self) -> bool:
        return self.role in {Role.MECHANIC.value, Role.OWNER.value, Role.ADMIN.value}

    @property
    def is_owner(self) -> bool:
        return self.role in {Role.OWNER.value, Role.ADMIN.value}


def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise UnauthorizedError("Missing Authorization header", code="AUTH_MISSING")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("Invalid auth scheme", code="AUTH_INVALID_SCHEME")
    return token


def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> CurrentUser:
    """Decode the JWT and return a :class:`CurrentUser`.

    Raises :class:`UnauthorizedError` if the token is missing/invalid/expired.
    """
    token = _extract_bearer(authorization)
    claims = decode_access_token(token)
    return CurrentUser(
        id=str(claims["sub"]),
        role=str(claims.get("role", Role.CUSTOMER.value)),
        center_id=claims.get("center_id"),
    )


def get_optional_user(
    authorization: Optional[str] = Header(default=None),
) -> Optional[CurrentUser]:
    """Like :func:`get_current_user` but returns ``None`` if absent."""
    if not authorization:
        return None
    try:
        return get_current_user(authorization=authorization)
    except UnauthorizedError:
        return None


def get_current_customer(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_customer:
        raise UnauthorizedError("Customer role required", code="AUTH_NOT_CUSTOMER")
    return user


def get_current_staff(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_staff:
        raise UnauthorizedError("Staff role required", code="AUTH_NOT_STAFF")
    return user


def get_current_owner(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_owner:
        raise UnauthorizedError("Owner role required", code="AUTH_NOT_OWNER")
    return user


# ---------------------------------------------------------------------------
# Redis async lifecycle helpers (used by main.py)
# ---------------------------------------------------------------------------
async def init_redis_clients() -> dict:
    """Create the fixed set of Redis clients once per process."""
    dbs = {
        settings.REDIS_CACHE_DB,
        settings.REDIS_OTP_DB,
        settings.REDIS_REFRESH_DB,
        settings.REDIS_PUBSUB_DB,
    }
    clients = {}
    for db in dbs:
        clients[db] = aioredis.from_url(
            settings.redis_url_for(db), encoding="utf-8", decode_responses=True
        )
    return clients


async def close_redis_clients(clients: dict) -> None:
    for client in clients.values():
        try:
            await client.aclose()  # redis>=5
        except AttributeError:
            await client.close()


# ---------------------------------------------------------------------------
# Type alias for route signatures
# ---------------------------------------------------------------------------
async def _noop_async() -> AsyncIterator[None]:
    yield None
