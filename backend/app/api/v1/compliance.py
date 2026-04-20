"""
CodeSentinel — Compliance API
Per-framework scores, violation summaries, and compliance posture over time.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.user import User

router = APIRouter()


@router.get("/compliance/summary")
async def compliance_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate compliance scores from the most recent completed scan per repo."""
    if not current_user.primary_org_id:
        return {"scores": {}}

    # Get latest completed scans per repo
    repo_ids_r = await db.execute(
        select(Repository.id).where(Repository.organization_id == current_user.primary_org_id)
    )
    repo_ids = [str(r[0]) for r in repo_ids_r.fetchall()]

    if not repo_ids:
        return {"scores": {}}

    # Aggregate compliance_results across latest scans
    scans_r = await db.execute(
        select(Scan)
        .where(
            Scan.repository_id.in_(repo_ids),
            Scan.status.in_(["completed", "blocked"]),
            Scan.compliance_results.isnot(None),
        )
        .order_by(Scan.created_at.desc())
        .limit(len(repo_ids) * 3)
    )
    scans = scans_r.scalars().all()

    # Merge compliance scores across all recent scans
    aggregated: dict[str, dict] = {}
    for scan in scans:
        if not scan.compliance_results:
            continue
        for framework, result in scan.compliance_results.items():
            if framework not in aggregated:
                aggregated[framework] = {
                    "passed": 0, "failed": 0, "score": 0,
                    "findings_count": 0, "scan_count": 0,
                }
            aggregated[framework]["passed"] += result.get("passed", 0)
            aggregated[framework]["failed"] += result.get("failed", 0)
            aggregated[framework]["scan_count"] += 1

    # Compute weighted score
    for fw, data in aggregated.items():
        total = data["passed"] + data["failed"]
        data["score"] = int((data["passed"] / total) * 100) if total > 0 else 100

    # Count open compliance findings by framework
    compliance_findings_r = await db.execute(
        select(Finding.compliance_frameworks, func.count(Finding.id))
        .join(Repository, Finding.repository_id == Repository.id)
        .where(
            Repository.organization_id == current_user.primary_org_id,
            Finding.agent_type == "compliance",
            Finding.status == "open",
        )
        .group_by(Finding.compliance_frameworks)
    )

    return {
        "scores": aggregated,
        "frameworks_checked": list(aggregated.keys()),
    }


@router.get("/compliance/findings")
async def compliance_findings(
    framework: str = Query(default=""),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get compliance-specific findings filtered by framework."""
    if not current_user.primary_org_id:
        return {"findings": [], "total": 0}

    q = (
        select(Finding)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(
            Repository.organization_id == current_user.primary_org_id,
            Finding.agent_type == "compliance",
            Finding.status == "open",
        )
    )

    if framework:
        # Filter by framework string in the JSON array
        q = q.where(Finding.compliance_frameworks.contains([framework]))

    total_r = await db.execute(
        select(func.count())
        .select_from(Finding)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(
            Repository.organization_id == current_user.primary_org_id,
            Finding.agent_type == "compliance",
            Finding.status == "open",
        )
    )
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
                "title": f.title,
                "severity": f.severity,
                "compliance_frameworks": f.compliance_frameworks or [],
                "compliance_details": f.compliance_details,
                "file_path": f.file_path,
                "line_start": f.line_start,
                "why_flagged": f.why_flagged,
                "recommendation": f.recommendation,
                "created_at": f.created_at.isoformat(),
            }
            for f in findings
        ],
        "total": total,
    }
