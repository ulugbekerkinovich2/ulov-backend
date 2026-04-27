"""Content repository."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.content.models import ContentPage


def list_by_kind(db: Session, *, kind: str, lang: str) -> List[ContentPage]:
    stmt = (
        select(ContentPage)
        .where(ContentPage.kind == kind, ContentPage.lang == lang)
        .order_by(ContentPage.slug)
    )
    return list(db.execute(stmt).scalars())


def get_by_slug(
    db: Session, *, kind: str, lang: str, slug: str
) -> Optional[ContentPage]:
    stmt = select(ContentPage).where(
        ContentPage.kind == kind,
        ContentPage.lang == lang,
        ContentPage.slug == slug,
    )
    return db.execute(stmt).scalar_one_or_none()


def upsert(
    db: Session,
    *,
    kind: str,
    lang: str,
    slug: str,
    title: str,
    body: dict,
) -> ContentPage:
    existing = get_by_slug(db, kind=kind, lang=lang, slug=slug)
    if existing is None:
        page = ContentPage(
            kind=kind, lang=lang, slug=slug, title=title, body=body
        )
        db.add(page)
        db.flush()
        return page
    existing.title = title
    existing.body = body
    db.flush()
    return existing
