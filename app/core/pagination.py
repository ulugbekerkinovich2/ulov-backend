"""Cursor and offset pagination helpers.

The wire envelope for list responses is::

    {"data": [...], "meta": {"count": 123, "next_cursor": "opaque"}}

See ``SYSTEM_ARCHITECTURE.md §5``.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")


class PageMeta(BaseModel):
    count: Optional[int] = None
    next_cursor: Optional[str] = None


class Page(GenericModel, Generic[T]):
    data: List[T]
    meta: PageMeta = PageMeta()


def encode_cursor(payload: Dict[str, Any]) -> str:
    """Opaque base64url JSON cursor. Never parsed by the client."""
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> Dict[str, Any]:
    padding = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
    return json.loads(raw.decode("utf-8"))


class OffsetParams(BaseModel):
    limit: int = 20
    offset: int = 0

    class Config:
        # Allow callers to pass int strings from query params.
        anystr_strip_whitespace = True

    @classmethod
    def clamp(cls, limit: int, offset: int, *, max_limit: int = 100) -> "OffsetParams":
        limit = max(1, min(limit or 20, max_limit))
        offset = max(0, offset or 0)
        return cls(limit=limit, offset=offset)
