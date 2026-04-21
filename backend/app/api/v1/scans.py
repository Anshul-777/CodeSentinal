"""
CodeSentinel — Scans API
List scans, trigger manual scans, get live agent state, view scan details.
"""
from __future__ import annotations

import uuid
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
log = structlog.get_logger("api.scans")


class ManualScanRequest(BaseModel):
    repository_id: str
    scope: str = "full"  # full|diff
    branch: Optional[str] = None


def _scan_detail(scan: Scan) -> dict:
    return {
        "id": scan.id,
        "repository_id": scan.repository_id,
        "trigger": scan.trigger,
        "pr_number": scan.pr_number,
        "pr_title": scan.pr_title,
        "pr_url": scan.pr_url,
        "pr_author": scan.pr_author,
        "branch": scan.branch,
        "base_branch": scan.base_branch,
        "commit_sha": scan.commit_sha,
        "commit_message": scan.commit_message,
        "compare_url": scan.compare_url,
        "status": scan.status,
        "risk_score": scan.risk_score,
        "risk_level": scan.risk_level,
        "findings_total": scan.findings_total,
        "findings_critical": scan.findings_critical,
        "findings_high": scan.findings_high,
        "findings_medium": scan.findings_medium,
        "findings_low": scan.findings_low,
        "findings_info": scan.findings_info,
        "secrets_found": scan.secrets_found,
        "dependencies_vulnerable": scan.dependencies_vulnerable,
        "fixes_available": scan.fixes_available,
        "fixes_applied": scan.fixes_applied,
        "agent_states": scan.agent_states,
        "agent_results": scan.agent_results,
        "agent_errors": scan.agent_errors,
        "agent_durations": scan.agent_durations,
        "compliance_results": scan.compliance_results,
        "merge_blocked": scan.merge_blocked,
        "merge_block_reason": scan.merge_block_reason,
        "check_run_url": scan.check_run_url,
        "ai_provider": scan.ai_provider,
        "ai_model": scan.ai_model,
        "ai_tokens_used": scan.ai_tokens_used,
        "files_scanned_count": scan.files_scanned_count,
        "lines_scanned": scan.lines_scanned,
        "duration_seconds": scan.duration_seconds,
        "queued_at": scan.queued_at.isoformat() if scan.queued_at else None,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "created_at": scan.created_at.isoformat(),
    }


@router.get("/scans")
async def list_scans(
    repository_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List scans for the user's organization, optionally filtered by repo or status."""
    if not current_user.primary_org_id:
        return {"scans": [], "total": 0}

    # Get repo IDs for this org
    repos_result = await db.execute(
        select(Repository.id).where(
            Repository.organization_id == current_user.primary_org_id
        )
    )
    repo_ids = [str(r[0]) for r in repos_result.fetchall()]
    if not repo_ids:
        return {"scans": [], "total": 0}

    query = select(Scan).where(Scan.repository_id.in_(repo_ids))
    count_query = select(func.count()).select_from(Scan).where(Scan.repository_id.in_(repo_ids))

    if repository_id:
        query = query.where(Scan.repository_id == repository_id)
        count_query = count_query.where(Scan.repository_id == repository_id)
    if status:
        query = query.where(Scan.status == status)
        count_query = count_query.where(Scan.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    scans_result = await db.execute(
        query.order_by(Scan.created_at.desc()).limit(limit).offset(offset)
    )
    scans = scans_result.scalars().all()

    return {"scans": [_scan_detail(s) for s in scans], "total": total, "limit": limit, "offset": offset}


@router.get("/scans/{scan_id}")
async def get_scan(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full scan details including agent states."""
    scan_result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")

    # Verify org ownership
    repo_result = await db.execute(
        select(Repository).where(
            Repository.id == scan.repository_id,
            Repository.organization_id == current_user.primary_org_id,
        )
    )
    if not repo_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Scan not found.")

    return _scan_detail(scan)


@router.get("/scans/{scan_id}/agent-status")
async def get_agent_status(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lightweight polling endpoint for the pipeline visualizer.
    Returns only agent states, status, and summary counts.
    """
    scan_result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")

    return {
        "scan_id": scan_id,
        "status": scan.status,
        "agent_states": scan.agent_states or {},
        "agent_durations": scan.agent_durations or {},
        "agent_errors": scan.agent_errors or {},
        "findings_total": scan.findings_total,
        "findings_critical": scan.findings_critical,
        "findings_high": scan.findings_high,
        "risk_score": scan.risk_score,
        "merge_blocked": scan.merge_blocked,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
    }


@router.post("/scans/manual", status_code=201)
async def trigger_manual_scan(
    payload: ManualScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual scan on a connected repository."""
    repo_result = await db.execute(
        select(Repository).where(
            Repository.id == payload.repository_id,
            Repository.organization_id == current_user.primary_org_id,
        )
    )
    repo = repo_result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")

    if not repo.scan_enabled:
        raise HTTPException(status_code=400, detail="Scanning is disabled for this repository.")

    # Estimate queue delay for user feedback.
    repo_ids_result = await db.execute(
        select(Repository.id).where(Repository.organization_id == current_user.primary_org_id)
    )
    org_repo_ids = [str(r[0]) for r in repo_ids_result.fetchall()]

    queued_count = 0
    running_count = 0
    avg_scan_seconds = 180
    if org_repo_ids:
        queued_count_r = await db.execute(
            select(func.count(Scan.id)).where(
                Scan.repository_id.in_(org_repo_ids),
                Scan.status == "queued",
            )
        )
        running_count_r = await db.execute(
            select(func.count(Scan.id)).where(
                Scan.repository_id.in_(org_repo_ids),
                Scan.status == "running",
            )
        )
        duration_avg_r = await db.execute(
            select(func.avg(Scan.duration_seconds)).where(
                Scan.repository_id.in_(org_repo_ids),
                Scan.duration_seconds.isnot(None),
                Scan.status.in_(["completed", "blocked"]),
            )
        )
        queued_count = int(queued_count_r.scalar() or 0)
        running_count = int(running_count_r.scalar() or 0)
        avg_duration = duration_avg_r.scalar()
        if avg_duration:
            avg_scan_seconds = max(60, int(float(avg_duration)))

    worker_slots = 4
    available_slots = max(0, worker_slots - running_count)
    if available_slots > 0:
        estimated_wait_seconds = 5
    else:
        estimated_wait_seconds = int(((queued_count + 1) / worker_slots) * avg_scan_seconds)

    estimated_total_seconds = estimated_wait_seconds + avg_scan_seconds

    scan_id = str(uuid.uuid4())
    scan = Scan(
        id=scan_id,
        repository_id=repo.id,
        trigger="manual",
        branch=payload.branch or repo.default_branch,
        scan_scope=payload.scope,
        status="queued",
        queued_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        agent_states={
            "static": "waiting",
            "dependency": "waiting",
            "business_logic": "waiting",
            "autofix": "waiting",
            "compliance": "waiting",
        },
    )
    db.add(scan)
    await db.commit()

    # Dispatch Celery task
    from app.tasks.scan_tasks import trigger_scan
    trigger_scan.delay(scan_id)

    log.info("Manual scan triggered", scan_id=scan_id, repo=repo.full_name, user=current_user.email)
    response = _scan_detail(scan)
    response.update(
        {
            "queue_position": queued_count + 1,
            "estimated_wait_seconds": estimated_wait_seconds,
            "estimated_total_seconds": estimated_total_seconds,
            "estimated_avg_scan_seconds": avg_scan_seconds,
        }
    )
    return response


@router.delete("/scans/{scan_id}")
async def cancel_scan(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a queued scan."""
    scan_result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")

    if scan.status not in ("queued", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel a scan with status '{scan.status}'.")

    scan.status = "cancelled"
    scan.completed_at = datetime.now(timezone.utc)
    await db.commit()

    if scan.celery_task_id:
        try:
            from app.core.celery_app import celery_app
            celery_app.control.revoke(scan.celery_task_id, terminate=True)
        except Exception:
            pass

    return {"message": "Scan cancelled.", "scan_id": scan_id}
