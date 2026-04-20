"""
CodeSentinel — Findings API
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.user import User

router = APIRouter()
log = structlog.get_logger("api.findings")


class FalsePositiveRequest(BaseModel):
    reason: str


class FindingStatusUpdate(BaseModel):
    status: str  # open|ignored|accepted_risk|fixed


def _finding_dict(f: Finding) -> dict:
    return {
        "id": f.id,
        "scan_id": f.scan_id,
        "repository_id": f.repository_id,
        "agent_type": f.agent_type,
        "rule_id": f.rule_id,
        "cve_id": f.cve_id,
        "cwe_id": f.cwe_id,
        "owasp_category": f.owasp_category,
        "title": f.title,
        "description": f.description,
        "business_risk": f.business_risk,
        "why_flagged": f.why_flagged,
        "recommendation": f.recommendation,
        "references": f.references or [],
        "file_path": f.file_path,
        "line_start": f.line_start,
        "line_end": f.line_end,
        "code_snippet": f.code_snippet,
        "code_context": f.code_context,
        "severity": f.severity,
        "cvss_score": f.cvss_score,
        "cvss_vector": f.cvss_vector,
        "confidence": f.confidence,
        "category": f.category,
        "compliance_frameworks": f.compliance_frameworks or [],
        "compliance_details": f.compliance_details,
        "dependency_name": f.dependency_name,
        "dependency_version": f.dependency_version,
        "dependency_fixed_version": f.dependency_fixed_version,
        "dependency_ecosystem": f.dependency_ecosystem,
        "secret_type": f.secret_type,
        "status": f.status,
        "is_false_positive": f.is_false_positive,
        "false_positive_reason": f.false_positive_reason,
        "fix_available": f.fix_available,
        "fix_complexity": f.fix_complexity,
        "first_seen_at": f.first_seen_at.isoformat() if f.first_seen_at else None,
        "last_seen_at": f.last_seen_at.isoformat() if f.last_seen_at else None,
        "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
        "created_at": f.created_at.isoformat(),
    }


def _build_org_finding_query(org_id: str):
    """Build a subquery to filter findings by org through repository ownership."""
    from sqlalchemy import and_
    return (
        select(Finding)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(Repository.organization_id == org_id)
    )


@router.get("/findings")
async def list_findings(
    scan_id: Optional[str] = Query(default=None),
    repository_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    agent_type: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.primary_org_id:
        return {"findings": [], "total": 0}

    q = _build_org_finding_query(current_user.primary_org_id)
    count_q = (
        select(func.count())
        .select_from(Finding)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(Repository.organization_id == current_user.primary_org_id)
    )

    for col, val in [
        (Finding.scan_id, scan_id),
        (Finding.repository_id, repository_id),
        (Finding.severity, severity),
        (Finding.agent_type, agent_type),
        (Finding.category, category),
        (Finding.status, status),
    ]:
        if val:
            q = q.where(col == val)
            count_q = count_q.where(col == val)

    if search:
        from sqlalchemy import or_
        pattern = f"%{search}%"
        q = q.where(or_(Finding.title.ilike(pattern), Finding.description.ilike(pattern), Finding.file_path.ilike(pattern)))
        count_q = count_q.where(or_(Finding.title.ilike(pattern), Finding.description.ilike(pattern), Finding.file_path.ilike(pattern)))

    total_r = await db.execute(count_q)
    total = total_r.scalar() or 0

    result = await db.execute(
        q.order_by(Finding.severity.asc(), Finding.created_at.desc())
        .limit(limit).offset(offset)
    )
    findings = result.scalars().all()
    return {"findings": [_finding_dict(f) for f in findings], "total": total, "limit": limit, "offset": offset}


@router.get("/findings/{finding_id}")
async def get_finding(
    finding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    # Verify ownership
    repo_r = await db.execute(
        select(Repository).where(
            Repository.id == finding.repository_id,
            Repository.organization_id == current_user.primary_org_id,
        )
    )
    if not repo_r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Finding not found.")

    return _finding_dict(finding)


@router.post("/findings/{finding_id}/false-positive")
async def mark_false_positive(
    finding_id: str,
    payload: FalsePositiveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a finding as a false positive with a reason."""
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    finding.is_false_positive = True
    finding.false_positive_reason = payload.reason[:499]
    finding.false_positive_reported_by = current_user.id
    finding.false_positive_at = datetime.now(timezone.utc)
    finding.status = "false_positive"
    await db.commit()

    log.info("Finding marked as false positive", finding_id=finding_id, user=current_user.email)
    return {"message": "Marked as false positive.", "finding_id": finding_id}


@router.patch("/findings/{finding_id}/status")
async def update_finding_status(
    finding_id: str,
    payload: FindingStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the lifecycle status of a finding."""
    valid_statuses = {"open", "ignored", "accepted_risk", "fixed"}
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")

    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    finding.status = payload.status
    if payload.status == "fixed":
        finding.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Status updated.", "status": payload.status}


@router.get("/findings/summary/by-org")
async def findings_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated findings summary for the dashboard — real DB queries."""
    if not current_user.primary_org_id:
        return {}

    base = (
        select(Finding.severity, func.count(Finding.id).label("count"))
        .join(Repository, Finding.repository_id == Repository.id)
        .where(
            Repository.organization_id == current_user.primary_org_id,
            Finding.status == "open",
            Finding.is_false_positive == False,
        )
        .group_by(Finding.severity)
    )
    result = await db.execute(base)
    by_severity = {row[0]: row[1] for row in result.fetchall()}

    by_agent = await db.execute(
        select(Finding.agent_type, func.count(Finding.id).label("count"))
        .join(Repository, Finding.repository_id == Repository.id)
        .where(Repository.organization_id == current_user.primary_org_id, Finding.status == "open")
        .group_by(Finding.agent_type)
    )
    by_agent_dict = {row[0]: row[1] for row in by_agent.fetchall()}

    by_category = await db.execute(
        select(Finding.category, func.count(Finding.id).label("count"))
        .join(Repository, Finding.repository_id == Repository.id)
        .where(Repository.organization_id == current_user.primary_org_id, Finding.status == "open", Finding.category.isnot(None))
        .group_by(Finding.category)
        .order_by(func.count(Finding.id).desc())
        .limit(10)
    )
    by_category_list = [{"category": row[0], "count": row[1]} for row in by_category.fetchall()]

    total_open = sum(by_severity.values())
    return {
        "total_open": total_open,
        "by_severity": {
            "critical": by_severity.get("critical", 0),
            "high": by_severity.get("high", 0),
            "medium": by_severity.get("medium", 0),
            "low": by_severity.get("low", 0),
            "info": by_severity.get("info", 0),
        },
        "by_agent": by_agent_dict,
        "by_category": by_category_list,
    }
