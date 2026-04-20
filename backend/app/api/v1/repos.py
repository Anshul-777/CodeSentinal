"""
CodeSentinel — Repositories API
Connect GitHub repos via App installation, list, configure scan policies,
view scan history, and disconnect.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import UserRole, get_current_user, require_role
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.user import User
from app.services.github_service import (
    GitHubAppError,
    get_installation_repos,
    get_installation_access_token,
)

router = APIRouter()
log = structlog.get_logger("api.repos")


class RepoConnectRequest(BaseModel):
    installation_id: str
    provider: str = "github"


class RepoConfigRequest(BaseModel):
    scan_enabled: Optional[bool] = None
    scan_on_pr: Optional[bool] = None
    scan_on_push: Optional[bool] = None
    auto_fix_enabled: Optional[bool] = None
    auto_fix_mode: Optional[str] = None
    block_on_critical: Optional[bool] = None
    block_on_high: Optional[bool] = None
    block_on_secret: Optional[bool] = None
    compliance_profiles: Optional[list[str]] = None
    scan_branches: Optional[list[str]] = None


def _repo_to_dict(repo: Repository) -> dict:
    return {
        "id": repo.id,
        "provider": repo.provider,
        "name": repo.name,
        "full_name": repo.full_name,
        "description": repo.description,
        "url": repo.url,
        "default_branch": repo.default_branch,
        "language": repo.language,
        "is_private": repo.is_private,
        "stars_count": repo.stars_count,
        "scan_enabled": repo.scan_enabled,
        "scan_on_pr": repo.scan_on_pr,
        "scan_on_push": repo.scan_on_push,
        "auto_fix_enabled": repo.auto_fix_enabled,
        "auto_fix_mode": repo.auto_fix_mode,
        "block_on_critical": repo.block_on_critical,
        "block_on_high": repo.block_on_high,
        "block_on_secret": repo.block_on_secret,
        "require_review_threshold": repo.require_review_threshold,
        "compliance_profiles": repo.compliance_profiles or [],
        "connection_status": repo.connection_status,
        "connection_error": repo.connection_error,
        "webhook_active": repo.webhook_active,
        "has_write_access": repo.has_write_access,
        "has_check_access": repo.has_check_access,
        "can_create_pr": repo.can_create_pr,
        "total_scans": repo.total_scans,
        "total_findings": repo.total_findings,
        "open_findings": repo.open_findings,
        "last_scan_at": repo.last_scan_at.isoformat() if repo.last_scan_at else None,
        "last_scan_risk_score": repo.last_scan_risk_score,
        "created_at": repo.created_at.isoformat(),
    }


@router.post("/repos/connect-github")
async def connect_github_installation(
    payload: RepoConnectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Connect a GitHub App installation to this organization.
    Fetches all accessible repos from the installation and persists them.
    """
    if not current_user.primary_org_id:
        raise HTTPException(status_code=400, detail="No organization found for this user.")

    # Verify the installation is accessible
    try:
        _, _ = await get_installation_access_token(payload.installation_id)
    except GitHubAppError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"GitHub installation not accessible: {exc}",
        )

    # Fetch repos from this installation
    try:
        github_repos = await get_installation_repos(payload.installation_id)
    except GitHubAppError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not fetch repositories: {exc}",
        )

    connected: list[dict] = []
    for gh_repo in github_repos:
        provider_id = str(gh_repo["id"])

        # Check if already connected
        existing = await db.execute(
            select(Repository).where(
                Repository.organization_id == current_user.primary_org_id,
                Repository.provider_repo_id == provider_id,
                Repository.provider == "github",
            )
        )
        existing_repo = existing.scalar_one_or_none()

        perms = gh_repo.get("permissions", {})

        if existing_repo:
            # Update permissions
            existing_repo.installation_id = payload.installation_id
            existing_repo.has_write_access = perms.get("push", False)
            existing_repo.has_check_access = perms.get("push", False)
            existing_repo.can_create_pr = perms.get("push", False)
            existing_repo.can_post_comments = perms.get("push", False)
            existing_repo.connection_status = "connected"
            existing_repo.updated_at = datetime.now(timezone.utc)
            connected.append(_repo_to_dict(existing_repo))
        else:
            new_repo = Repository(
                id=str(uuid.uuid4()),
                organization_id=current_user.primary_org_id,
                provider="github",
                provider_repo_id=provider_id,
                name=gh_repo["name"],
                full_name=gh_repo["full_name"],
                description=gh_repo.get("description", ""),
                url=gh_repo.get("html_url", ""),
                clone_url=gh_repo.get("clone_url", ""),
                default_branch=gh_repo.get("default_branch", "main"),
                language=gh_repo.get("language"),
                is_private=gh_repo.get("private", True),
                stars_count=gh_repo.get("stargazers_count", 0),
                installation_id=payload.installation_id,
                has_read_access=True,
                has_write_access=perms.get("push", False),
                has_check_access=perms.get("push", False),
                can_create_pr=perms.get("push", False),
                can_post_comments=perms.get("push", False),
                webhook_active=True,
                connection_status="connected",
                scan_enabled=True,
                scan_on_pr=True,
                block_on_critical=True,
                block_on_secret=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(new_repo)
            connected.append(_repo_to_dict(new_repo))

    await db.commit()
    log.info("GitHub installation connected", installation_id=payload.installation_id, repos=len(connected))
    return {"connected": len(connected), "repositories": connected}


@router.get("/repos")
async def list_repos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all repositories connected to the current user's organization."""
    if not current_user.primary_org_id:
        return {"repositories": [], "total": 0}

    result = await db.execute(
        select(Repository)
        .where(Repository.organization_id == current_user.primary_org_id)
        .order_by(Repository.created_at.desc())
    )
    repos = result.scalars().all()
    return {"repositories": [_repo_to_dict(r) for r in repos], "total": len(repos)}


@router.get("/repos/{repo_id}")
async def get_repo(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific repository by ID."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id,
            Repository.organization_id == current_user.primary_org_id,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")
    return _repo_to_dict(repo)


@router.patch("/repos/{repo_id}")
async def update_repo_config(
    repo_id: str,
    payload: RepoConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update repository scan configuration and policy settings."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id,
            Repository.organization_id == current_user.primary_org_id,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(repo, field, value)
    repo.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _repo_to_dict(repo)


@router.delete("/repos/{repo_id}")
async def disconnect_repo(
    repo_id: str,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a repository. Requires admin role."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id,
            Repository.organization_id == current_user.primary_org_id,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")

    await db.delete(repo)
    await db.commit()
    return {"message": f"Repository '{repo.full_name}' disconnected successfully."}


@router.get("/repos/{repo_id}/scans")
async def get_repo_scan_history(
    repo_id: str,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get scan history for a repository."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id,
            Repository.organization_id == current_user.primary_org_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Repository not found.")

    scans_result = await db.execute(
        select(Scan)
        .where(Scan.repository_id == repo_id)
        .order_by(Scan.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    scans = scans_result.scalars().all()

    count_result = await db.execute(
        select(func.count()).where(Scan.repository_id == repo_id)
    )
    total = count_result.scalar() or 0

    return {
        "scans": [_scan_to_dict(s) for s in scans],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _scan_to_dict(scan: Scan) -> dict:
    return {
        "id": scan.id,
        "trigger": scan.trigger,
        "pr_number": scan.pr_number,
        "pr_title": scan.pr_title,
        "branch": scan.branch,
        "commit_sha": scan.commit_sha,
        "status": scan.status,
        "risk_score": scan.risk_score,
        "risk_level": scan.risk_level,
        "findings_total": scan.findings_total,
        "findings_critical": scan.findings_critical,
        "findings_high": scan.findings_high,
        "findings_medium": scan.findings_medium,
        "findings_low": scan.findings_low,
        "secrets_found": scan.secrets_found,
        "merge_blocked": scan.merge_blocked,
        "agent_states": scan.agent_states,
        "duration_seconds": scan.duration_seconds,
        "created_at": scan.created_at.isoformat(),
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
    }
