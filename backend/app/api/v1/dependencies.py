"""
CodeSentinel — Dependencies API
Dedicated endpoint for dependency-specific findings from Agent 2.
Wraps the findings endpoint with dependency-specific aggregation.
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


@router.get("/dependencies")
async def list_dependency_findings(
    repository_id: Optional[str] = Query(default=None),
    ecosystem: Optional[str] = Query(default=None),
    has_cve: Optional[bool] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dependency findings with optional filters."""
    if not current_user.primary_org_id:
        return {"findings": [], "total": 0}

    q = (
        select(Finding)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(
            Repository.organization_id == current_user.primary_org_id,
            Finding.agent_type == "dependency",
        )
    )

    if repository_id:
        q = q.where(Finding.repository_id == repository_id)
    if ecosystem:
        q = q.where(Finding.dependency_ecosystem == ecosystem)
    if severity:
        q = q.where(Finding.severity == severity)
    if has_cve is not None:
        if has_cve:
            q = q.where(Finding.cve_id.isnot(None))
        else:
            q = q.where(Finding.cve_id.is_(None))

    count_q = (
        select(func.count())
        .select_from(Finding)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(
            Repository.organization_id == current_user.primary_org_id,
            Finding.agent_type == "dependency",
        )
    )

    total_r = await db.execute(count_q)
    total = total_r.scalar() or 0

    result = await db.execute(
        q.order_by(Finding.severity.asc(), Finding.created_at.desc())
        .limit(limit).offset(offset)
    )
    findings = result.scalars().all()

    return {
        "findings": [
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
                "cvss_score": f.cvss_score,
                "category": f.category,
                "cve_id": f.cve_id,
                "dependency_name": f.dependency_name,
                "dependency_version": f.dependency_version,
                "dependency_fixed_version": f.dependency_fixed_version,
                "dependency_ecosystem": f.dependency_ecosystem,
                "file_path": f.file_path,
                "status": f.status,
                "fix_available": f.fix_available,
                "fix_complexity": f.fix_complexity,
                "references": f.references or [],
                "first_seen_at": f.first_seen_at.isoformat() if f.first_seen_at else None,
                "created_at": f.created_at.isoformat(),
            }
            for f in findings
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/dependencies/ecosystems")
async def list_ecosystems(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return distinct ecosystems found in dependency findings."""
    if not current_user.primary_org_id:
        return {"ecosystems": []}

    result = await db.execute(
        select(Finding.dependency_ecosystem, func.count(Finding.id).label("count"))
        .join(Repository, Finding.repository_id == Repository.id)
        .where(
            Repository.organization_id == current_user.primary_org_id,
            Finding.agent_type == "dependency",
            Finding.dependency_ecosystem.isnot(None),
        )
        .group_by(Finding.dependency_ecosystem)
        .order_by(func.count(Finding.id).desc())
    )
    return {"ecosystems": [{"name": row[0], "count": row[1]} for row in result.fetchall()]}
