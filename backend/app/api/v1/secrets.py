"""
CodeSentinel — Secrets API
Dedicated endpoint aggregating secret-type findings from Agent 1.
Secret findings are always critical — immediate action required.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.user import User

router = APIRouter()


@router.get("/secrets")
async def list_secrets(
    repository_id: Optional[str] = Query(default=None),
    secret_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all secret findings for the organization."""
    if not current_user.primary_org_id:
        return {"secrets": [], "total": 0}

    # Secrets are findings with category='secrets' or agent_type='secret'
    from sqlalchemy import or_

    q = (
        select(Finding)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(
            Repository.organization_id == current_user.primary_org_id,
            or_(Finding.category == "secrets", Finding.agent_type == "secret"),
        )
    )

    if repository_id:
        q = q.where(Finding.repository_id == repository_id)
    if secret_type:
        q = q.where(Finding.secret_type == secret_type)
    if status:
        q = q.where(Finding.status == status)
    else:
        q = q.where(Finding.status != "false_positive")

    count_q = (
        select(func.count())
        .select_from(Finding)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(
            Repository.organization_id == current_user.primary_org_id,
            or_(Finding.category == "secrets", Finding.agent_type == "secret"),
        )
    )

    total_r = await db.execute(count_q)
    total = total_r.scalar() or 0

    result = await db.execute(
        q.order_by(Finding.created_at.desc()).limit(limit).offset(offset)
    )
    findings = result.scalars().all()

    return {
        "secrets": [
            {
                "id": f.id,
                "scan_id": f.scan_id,
                "repository_id": f.repository_id,
                "title": f.title,
                "description": f.description,
                "why_flagged": f.why_flagged,
                "business_risk": f.business_risk,
                "recommendation": f.recommendation,
                "severity": f.severity,
                "secret_type": f.secret_type,
                "secret_verified": f.secret_verified,
                "file_path": f.file_path,
                "line_start": f.line_start,
                "status": f.status,
                "is_false_positive": f.is_false_positive,
                "first_seen_at": f.first_seen_at.isoformat() if f.first_seen_at else None,
                "created_at": f.created_at.isoformat(),
            }
            for f in findings
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/secrets/types")
async def secret_type_breakdown(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Count secrets by type for the summary widget."""
    if not current_user.primary_org_id:
        return {"types": []}

    from sqlalchemy import or_

    result = await db.execute(
        select(Finding.secret_type, func.count(Finding.id).label("count"))
        .join(Repository, Finding.repository_id == Repository.id)
        .where(
            Repository.organization_id == current_user.primary_org_id,
            or_(Finding.category == "secrets", Finding.agent_type == "secret"),
            Finding.secret_type.isnot(None),
            Finding.status != "false_positive",
        )
        .group_by(Finding.secret_type)
        .order_by(func.count(Finding.id).desc())
    )
    return {"types": [{"secret_type": row[0], "count": row[1]} for row in result.fetchall()]}
