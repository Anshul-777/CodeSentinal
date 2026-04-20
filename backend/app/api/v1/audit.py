"""
CodeSentinel — Audit Logs API
Immutable append-only audit trail for all security-relevant actions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter()


def _log_dict(l: AuditLog) -> dict:
    return {
        "id": l.id,
        "organization_id": l.organization_id,
        "user_id": l.user_id,
        "actor_email": l.actor_email,
        "actor_role": l.actor_role,
        "action": l.action,
        "resource_type": l.resource_type,
        "resource_id": l.resource_id,
        "resource_name": l.resource_name,
        "details": l.details,
        "result": l.result,
        "error_message": l.error_message,
        "ip_address": l.ip_address,
        "user_agent": l.user_agent,
        "request_id": l.request_id,
        "created_at": l.created_at.isoformat(),
    }


@router.get("/audit")
async def list_audit_logs(
    search: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    resource_type: Optional[str] = Query(default=None),
    result: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List audit logs for the current organization with filtering."""
    if not current_user.primary_org_id:
        return {"logs": [], "total": 0}

    q = select(AuditLog).where(AuditLog.organization_id == current_user.primary_org_id)
    count_q = (
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.organization_id == current_user.primary_org_id)
    )

    if action:
        q = q.where(AuditLog.action == action)
        count_q = count_q.where(AuditLog.action == action)

    if resource_type:
        q = q.where(AuditLog.resource_type == resource_type)
        count_q = count_q.where(AuditLog.resource_type == resource_type)

    if result:
        q = q.where(AuditLog.result == result)
        count_q = count_q.where(AuditLog.result == result)

    if search:
        from sqlalchemy import or_
        pattern = f"%{search}%"
        q = q.where(or_(
            AuditLog.action.ilike(pattern),
            AuditLog.actor_email.ilike(pattern),
            AuditLog.resource_name.ilike(pattern),
        ))
        count_q = count_q.where(or_(
            AuditLog.action.ilike(pattern),
            AuditLog.actor_email.ilike(pattern),
            AuditLog.resource_name.ilike(pattern),
        ))

    total_r = await db.execute(count_q)
    total = total_r.scalar() or 0

    result_q = await db.execute(
        q.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    )
    logs = result_q.scalars().all()

    return {
        "logs": [_log_dict(l) for l in logs],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit/actions")
async def list_audit_actions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all distinct action types that have been logged — useful for filtering UI."""
    if not current_user.primary_org_id:
        return {"actions": []}

    result = await db.execute(
        select(AuditLog.action)
        .where(AuditLog.organization_id == current_user.primary_org_id)
        .distinct()
        .order_by(AuditLog.action)
    )
    actions = [row[0] for row in result.fetchall()]
    return {"actions": actions}


async def write_audit_log(
    db,
    action: str,
    user: Optional[User] = None,
    organization_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    details: Optional[dict] = None,
    result: str = "success",
    error: Optional[str] = None,
    ip_address: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """Helper to write an audit log entry. Used by other API modules."""
    entry = AuditLog(
        id=str(uuid.uuid4()),
        organization_id=organization_id or (user.primary_org_id if user else None),
        user_id=user.id if user else None,
        actor_email=user.email if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        details=details,
        result=result,
        error_message=error,
        ip_address=ip_address,
        request_id=request_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
