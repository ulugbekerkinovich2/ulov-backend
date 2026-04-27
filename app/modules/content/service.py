"""Content domain logic. Read-through cache lives here."""

from __future__ import annotations

import json
from typing import Any, List, Optional

from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.content import repository as repo
from app.modules.content.models import CONTENT_KINDS, ContentPage

log = get_logger(__name__)

CACHE_TTL_SECONDS = 600  # 10 min — short window; invalidate on admin edits in P6.


def _cache_key(kind: str, lang: str) -> str:
    return f"content:{kind}:{lang}"


def _validate_kind(kind: str) -> None:
    if kind not in CONTENT_KINDS:
        from app.core.errors import NotFoundError

        raise NotFoundError(
            f"Unknown content kind '{kind}'", code="CONTENT_UNKNOWN_KIND"
        )


async def list_pages(
    db: Session, redis: Optional[Redis], *, kind: str, lang: str
) -> List[dict]:
    _validate_kind(kind)

    if redis is not None:
        cached = await redis.get(_cache_key(kind, lang))
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                log.warning("content_cache_decode_error", kind=kind, lang=lang)

    pages: List[ContentPage] = repo.list_by_kind(db, kind=kind, lang=lang)
    # Serialise to the dict shape that matches ``ContentPageOut``.
    payload: List[dict] = [
        {
            "id": str(p.id),
            "kind": p.kind,
            "lang": p.lang,
            "slug": p.slug,
            "title": p.title,
            "body": p.body,
            "updated_at": p.updated_at.isoformat(),
        }
        for p in pages
    ]

    if redis is not None:
        await redis.setex(
            _cache_key(kind, lang), CACHE_TTL_SECONDS, json.dumps(payload)
        )
    return payload


def upsert_page(
    db: Session,
    *,
    kind: str,
    lang: str,
    slug: str,
    title: str,
    body: Any,
) -> ContentPage:
    _validate_kind(kind)
    return repo.upsert(
        db, kind=kind, lang=lang, slug=slug, title=title, body=body
    )
