"""Audit logging helper.

Call ``record(db, ...)`` from any module that wants to leave a trail. Keeps
the call site short and the JSON serialisation in one place. Failures are
swallowed — auditing should never break the user-visible operation.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.deps import CurrentUser
from app.modules.audit.models import AuditLog

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


def _safe(value: Any) -> Any:
    """Coerce arbitrary values into JSON-serialisable shapes."""
    if value is None:
        return None
    try:
        return json.loads(json.dumps(value, default=str))
    except (TypeError, ValueError):
        return str(value)


def record(
    db: Session,
    *,
    actor: Optional[CurrentUser],
    action: str,
    entity_type: str,
    entity_id: Optional[UUIDLike] = None,
    before: Any = None,
    after: Any = None,
    meta: Any = None,
) -> None:
    """Append an audit row. Never raises."""
    try:
        actor_id = None
        actor_role = None
        if actor is not None:
            actor_role = actor.role
            # Mechanic JWT 'sub' isn't a User row; keep actor_user_id null.
            if actor.role != "mechanic":
                actor_id = actor.id
        db.add(
            AuditLog(
                actor_user_id=actor_id,
                actor_role=actor_role,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                before=_safe(before),
                after=_safe(after),
                meta=_safe(meta),
            )
        )
        db.flush()
    except Exception:  # noqa: BLE001
        log.exception(
            "audit_record_failed",
            action=action,
            entity_type=entity_type,
        )
