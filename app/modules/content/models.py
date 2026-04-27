"""CMS-style content pages (traffic rules, signs, fines, tips).

Frontend currently ships this data in TypeScript files. Moving it here lets
admin staff edit without a deploy, and lets us localise / version it.
"""

from __future__ import annotations

from sqlalchemy import Column, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.modules.content.stories_models import Story  # noqa: F401

CONTENT_KINDS = ("traffic_rules", "road_signs", "fines", "tips")

content_kind_enum = PG_ENUM(
    *CONTENT_KINDS,
    name="content_kind",
    create_type=True,
)


class ContentPage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_pages"
    __table_args__ = (
        UniqueConstraint(
            "kind", "lang", "slug", name="uq_content_pages_kind_lang_slug"
        ),
    )

    kind = Column(content_kind_enum, nullable=False, index=True)
    lang = Column(String(2), nullable=False)  # uz | ru | en
    slug = Column(String(120), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(JSONB, nullable=False)  # shape differs per kind
