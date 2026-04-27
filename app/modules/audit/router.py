"""Audit log read endpoints — admin-only."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import Role, require_role
from app.deps import get_db
from app.modules.audit.models import AuditLog

router = APIRouter()


@router.get(
    "/audit-logs",
    response_model=List[Dict[str, Any]],
    summary="Browse the audit trail (admin only)",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def list_audit_logs(
    entity_type: Optional[str] = Query(None, max_length=64),
    entity_id: Optional[UUID] = None,
    actor_user_id: Optional[UUID] = None,
    action: Optional[str] = Query(None, max_length=64),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    stmt = select(AuditLog).order_by(AuditLog.at.desc()).limit(limit).offset(offset)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if date_from:
        stmt = stmt.where(AuditLog.at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.at <= date_to)

    out: List[Dict[str, Any]] = []
    for row in db.execute(stmt).scalars():
        out.append(
            {
                "id": str(row.id),
                "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
                "actor_role": row.actor_role,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": str(row.entity_id) if row.entity_id else None,
                "before": row.before,
                "after": row.after,
                "meta": row.meta,
                "at": row.at.isoformat() if row.at else None,
            }
        )
    return out
