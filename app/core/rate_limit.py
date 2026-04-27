"""Redis-backed rate limiter.

A simple fixed-window counter is sufficient for our current scale (auth, writes,
reads). If we need smoother behaviour (bursts allowed up to a ceiling), switch
to a leaky-bucket or GCRA algorithm — keys and deps stay the same.
"""

from __future__ import annotations

import time
from typing import Awaitable, Callable, Optional

from fastapi import Request

from app.core.errors import RateLimitedError


# The Redis client is injected — we don't import here to avoid circular deps.
# See app/deps.py::get_redis.
RedisLike = object  # loose alias for typing clarity


async def check_rate_limit(
    redis: "RedisLike",
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Increment a counter and raise if it exceeds ``limit``.

    Redis key expires at the end of the current window. The first caller in a
    new window sees ``value == 1`` and sets the expiry.
    """
    full_key = f"rl:{key}:{int(time.time()) // window_seconds}"
    pipe = redis.pipeline()  # type: ignore[attr-defined]
    pipe.incr(full_key, 1)
    pipe.expire(full_key, window_seconds)
    value, _ = await pipe.execute()
    if int(value) > limit:
        raise RateLimitedError(
            "Too many requests",
            code="RATE_LIMITED",
            details={"limit": limit, "window_seconds": window_seconds},
        )


def rate_limit_dependency(
    *,
    key_builder: Callable[[Request], str],
    limit: int,
    window_seconds: int = 60,
) -> Callable[[Request], Awaitable[None]]:
    """Build a FastAPI dependency from a key-building callable.

    Example — 5 auth attempts per minute per IP::

        IpLimit = rate_limit_dependency(
            key_builder=lambda r: f"auth:ip:{r.client.host}",
            limit=5,
        )

        @router.post("/login", dependencies=[Depends(IpLimit)])
        def login(...): ...
    """
    from app.deps import get_redis  # local import to avoid cycles

    async def _dep(request: Request) -> None:
        redis = await get_redis()
        await check_rate_limit(
            redis,
            key=key_builder(request),
            limit=limit,
            window_seconds=window_seconds,
        )

    return _dep


def client_ip(request: Request) -> str:
    """Best-effort client IP extraction respecting proxy headers.

    We trust ``X-Forwarded-For`` because uvicorn is launched with
    ``--proxy-headers --forwarded-allow-ips=*`` behind nginx/Cloudflare.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def client_phone_key(phone: Optional[str]) -> str:
    return f"phone:{phone}" if phone else "phone:unknown"
