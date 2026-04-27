"""Structured logging setup.

We emit JSON in prod (so Loki / Elastic can parse it without a regex) and
human-readable key=value in dev. A ``request_id`` contextvar propagates
through the call graph; the FastAPI middleware binds it per request.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any, Optional

import structlog

from app.config import settings

_request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def bind_request_id(request_id: Optional[str]) -> None:
    _request_id_ctx.set(request_id)


def current_request_id() -> Optional[str]:
    return _request_id_ctx.get()


def _add_request_id(_: Any, __: str, event_dict: dict) -> dict:
    rid = _request_id_ctx.get()
    if rid is not None:
        event_dict.setdefault("request_id", rid)
    return event_dict


def configure_logging() -> None:
    """Wire up stdlib ``logging`` and ``structlog`` once at startup."""
    level = getattr(logging, settings.APP_LOG_LEVEL.upper(), logging.INFO)

    # stdlib: single handler to stdout, no default formatting
    # (structlog renders the final string/json itself).
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy third parties
    for noisy in ("uvicorn.access", "urllib3", "boto3", "botocore", "s3transfer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_request_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if settings.APP_LOG_JSON or settings.is_prod:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
