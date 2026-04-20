"""
CodeSentinel — Auto-Fix API
Manage fix records, apply verified fixes to repositories, reject fixes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.fix import Fix
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.user import User

router = APIRouter()
log = structlog.get_logger("api.autofix")


def _fix_dict(fix: Fix) -> dict:
    return {
        "id": fix.id,
        "finding_id": fix.finding_id,
        "scan_id": fix.scan_id,
        "fix_type": fix.fix_type,
        "fix_strategy": fix.fix_strategy,
        "file_path": fix.file_path,
        "original_code": fix.original_code,
        "fixed_code": fix.fixed_code,
        "diff_patch": fix.diff_patch,
        "diff_stats": fix.diff_stats,
        "description": fix.description,
        "why_safe": fix.why_safe,
        "step_by_step": fix.step_by_step,
        "sandbox_status": fix.sandbox_status,
        "sandbox_test_output": fix.sandbox_test_output,
        "sandbox_lint_output": fix.sandbox_lint_output,
        "sandbox_duration_seconds": fix.sandbox_duration_seconds,
        "sandbox_checks_passed": fix.sandbox_checks_passed or [],
        "sandbox_checks_failed": fix.sandbox_checks_failed or [],
        "tests_passed": fix.tests_passed,
        "tests_failed": fix.tests_failed,
        "tests_run": fix.tests_run,
        "status": fix.status,
        "fix_branch": fix.fix_branch,
        "fix_commit_sha": fix.fix_commit_sha,
        "fix_pr_number": fix.fix_pr_number,
        "fix_pr_url": fix.fix_pr_url,
        "is_verified": fix.is_verified,
        "verification_method": fix.verification_method,
        "ai_provider": fix.ai_provider,
        "ai_model": fix.ai_model,
        "created_at": fix.created_at.isoformat(),
        "applied_at": fix.applied_at.isoformat() if fix.applied_at else None,
    }


@router.get("/autofix")
async def list_fixes(
    finding_id: Optional[str] = Query(default=None),
    scan_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List auto-fix records for the user's organization."""
    if not current_user.primary_org_id:
        return {"fixes": [], "total": 0}

    # Join through finding → repository → organization
    q = (
        select(Fix)
        .join(Finding, Fix.finding_id == Finding.id)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(Repository.organization_id == current_user.primary_org_id)
    )

    if finding_id:
        q = q.where(Fix.finding_id == finding_id)
    if scan_id:
        q = q.where(Fix.scan_id == scan_id)
    if status:
        q = q.where(Fix.status == status)

    count_q = (
        select(func.count())
        .select_from(Fix)
        .join(Finding, Fix.finding_id == Finding.id)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(Repository.organization_id == current_user.primary_org_id)
    )

    total_r = await db.execute(count_q)
    total = total_r.scalar() or 0

    result = await db.execute(
        q.order_by(Fix.created_at.desc()).limit(limit).offset(offset)
    )
    fixes = result.scalars().all()

    return {
        "fixes": [_fix_dict(f) for f in fixes],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/autofix/{fix_id}")
async def get_fix(
    fix_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Fix).where(Fix.id == fix_id))
    fix = result.scalar_one_or_none()
    if not fix:
        raise HTTPException(status_code=404, detail="Fix not found.")
    return _fix_dict(fix)


@router.post("/autofix/{fix_id}/apply")
async def apply_fix(
    fix_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Apply a verified fix to the connected repository.
    Creates a fix branch and optionally opens a PR depending on repo config.
    """
    result = await db.execute(select(Fix).where(Fix.id == fix_id))
    fix = result.scalar_one_or_none()
    if not fix:
        raise HTTPException(status_code=404, detail="Fix not found.")

    if fix.status not in ("verified",):
        raise HTTPException(
            status_code=400,
            detail=f"Fix must be verified before applying. Current status: {fix.status}",
        )

    # Get the associated repository
    finding_r = await db.execute(select(Finding).where(Finding.id == fix.finding_id))
    finding = finding_r.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Associated finding not found.")

    repo_r = await db.execute(select(Repository).where(Repository.id == finding.repository_id))
    repo = repo_r.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")

    if not repo.has_write_access or not repo.installation_id:
        # No write access — return the patch for manual application
        fix.status = "applied"
        fix.applied_at = datetime.now(timezone.utc)
        fix.applied_by_user_id = current_user.id
        fix.application_error = "No write access — patch available for manual application"
        await db.commit()
        return {
            "status": "patch_ready",
            "message": "Write access not available. Use the diff_patch to apply manually.",
            "diff_patch": fix.diff_patch,
            "step_by_step": fix.step_by_step,
        }

    # Attempt to push fix branch to GitHub
    try:
        from app.services.github_service import create_fix_branch_and_pr, fetch_file_content

        if not fix.file_path or not fix.fixed_code:
            raise ValueError("Fix has no file path or fixed code content.")

        # Fetch original file SHA for the update API
        file_content = await fetch_file_content(
            repo.installation_id, repo.full_name, fix.file_path
        )

        # Get file SHA
        import httpx
        from app.services.github_service import get_authenticated_headers, GITHUB_API
        headers = await get_authenticated_headers(repo.installation_id)
        async with httpx.AsyncClient(timeout=15.0) as client:
            meta_r = await client.get(
                f"{GITHUB_API}/repos/{repo.full_name}/contents/{fix.file_path}",
                headers=headers,
            )
            meta_r.raise_for_status()
            original_sha = meta_r.json()["sha"]

        branch_name = f"{repo.auto_fix_branch_prefix}-{fix_id[:8]}"
        commit_msg = f"fix: CodeSentinel auto-fix for {finding.rule_id or 'vulnerability'}\n\n{fix.description or ''}"
        pr_title = f"[CodeSentinel] Fix: {finding.title[:100]}"
        pr_body = (
            f"## CodeSentinel Auto-Fix\n\n"
            f"**Finding:** {finding.title}\n"
            f"**Severity:** {finding.severity.upper()}\n"
            f"**Rule:** {finding.rule_id or 'N/A'}\n\n"
            f"### What was fixed\n{fix.description or 'See diff'}\n\n"
            f"### Why this fix is safe\n{fix.why_safe or 'Sandbox validation passed'}\n\n"
            f"### Sandbox Results\n"
            f"- Checks passed: {', '.join(fix.sandbox_checks_passed or [])}\n"
            f"- Verification: {fix.verification_method or 'sandbox'}\n\n"
            f"*This PR was automatically generated and verified by CodeSentinel.*"
        )

        pr_data = await create_fix_branch_and_pr(
            installation_id=repo.installation_id,
            repo_full_name=repo.full_name,
            base_branch=repo.default_branch,
            branch_name=branch_name,
            file_path=fix.file_path,
            fixed_content=fix.fixed_code,
            original_sha=original_sha,
            commit_message=commit_msg,
            pr_title=pr_title,
            pr_body=pr_body,
        )

        fix.status = "applied"
        fix.fix_branch = branch_name
        fix.fix_pr_number = pr_data.get("number")
        fix.fix_pr_url = pr_data.get("html_url")
        fix.applied_at = datetime.now(timezone.utc)
        fix.applied_by_user_id = current_user.id
        await db.commit()

        log.info("Fix applied to repository", fix_id=fix_id, pr_url=fix.fix_pr_url)

        return {
            "status": "applied",
            "fix_pr_url": fix.fix_pr_url,
            "fix_pr_number": fix.fix_pr_number,
            "fix_branch": branch_name,
            "message": f"Fix branch created and PR opened: {fix.fix_pr_url}",
        }

    except Exception as exc:
        log.error("Failed to apply fix to repository", fix_id=fix_id, error=str(exc))
        fix.application_error = str(exc)
        await db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to apply fix to repository: {str(exc)[:200]}",
        )


@router.post("/autofix/{fix_id}/reject")
async def reject_fix(
    fix_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a fix as user-rejected."""
    result = await db.execute(select(Fix).where(Fix.id == fix_id))
    fix = result.scalar_one_or_none()
    if not fix:
        raise HTTPException(status_code=404, detail="Fix not found.")

    fix.status = "user_rejected"
    fix.rejected_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "user_rejected", "fix_id": fix_id}


@router.get("/autofix/stats/summary")
async def autofix_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Summary of auto-fix statistics for the dashboard."""
    if not current_user.primary_org_id:
        return {}

    base = (
        select(Fix.status, func.count(Fix.id).label("count"))
        .join(Finding, Fix.finding_id == Finding.id)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(Repository.organization_id == current_user.primary_org_id)
        .group_by(Fix.status)
    )
    result = await db.execute(base)
    by_status = {row[0]: row[1] for row in result.fetchall()}

    return {
        "total": sum(by_status.values()),
        "verified": by_status.get("verified", 0),
        "applied": by_status.get("applied", 0),
        "rejected": by_status.get("user_rejected", 0) + by_status.get("rejected", 0),
        "pending": by_status.get("pending", 0),
        "sandbox_failed": by_status.get("rejected", 0),
    }
