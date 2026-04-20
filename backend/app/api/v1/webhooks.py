"""
CodeSentinel — Webhook Receiver
Validates and processes GitHub App webhooks.
Queues Celery scan jobs. Does NOT process inline (async, fast response).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from sqlalchemy import select

from app.core.database import get_db_context
from app.core.security import verify_github_signature
from app.models.repository import Repository
from app.models.scan import Scan

router = APIRouter()
log = structlog.get_logger("api.webhooks")


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
    x_github_delivery: str = Header(default=""),
):
    """
    Receive GitHub App webhook events.
    Validates HMAC-SHA256 signature before processing.
    Queues a Celery scan job for relevant events.
    Returns 200 immediately — processing is async.
    """
    body = await request.body()

    # ── Signature validation ───────────────────────────────────────
    if not verify_github_signature(body, x_hub_signature_256):
        log.warning(
            "GitHub webhook signature validation failed",
            delivery=x_github_delivery,
            event=x_github_event,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature verification failed.",
        )

    # Parse payload
    try:
        import orjson
        payload: dict[str, Any] = orjson.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    log.info(
        "GitHub webhook received",
        event=x_github_event,
        delivery=x_github_delivery,
        action=payload.get("action"),
    )

    # ── Route by event type ────────────────────────────────────────
    if x_github_event == "pull_request":
        action = payload.get("action", "")
        if action in ("opened", "synchronize", "reopened"):
            background_tasks.add_task(
                _handle_pull_request_event, payload, x_github_delivery
            )
    elif x_github_event == "push":
        background_tasks.add_task(_handle_push_event, payload, x_github_delivery)
    elif x_github_event == "installation":
        background_tasks.add_task(_handle_installation_event, payload)
    elif x_github_event == "installation_repositories":
        background_tasks.add_task(_handle_installation_repos_event, payload)
    elif x_github_event == "ping":
        log.info("GitHub App ping received", zen=payload.get("zen", ""))

    return {"received": True, "event": x_github_event, "delivery": x_github_delivery}


async def _handle_pull_request_event(payload: dict, delivery_id: str) -> None:
    """Create a scan job for an opened/updated PR."""
    pr = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})
    installation = payload.get("installation", {})

    provider_repo_id = str(repo_data.get("id", ""))
    installation_id = str(installation.get("id", ""))

    async with get_db_context() as db:
        # Find repository by provider ID
        result = await db.execute(
            select(Repository).where(
                Repository.provider_repo_id == provider_repo_id,
                Repository.provider == "github",
            )
        )
        repo = result.scalar_one_or_none()

        if not repo:
            log.info(
                "PR webhook: repository not connected to CodeSentinel",
                provider_repo_id=provider_repo_id,
                full_name=repo_data.get("full_name"),
            )
            return

        if not repo.scan_enabled or not repo.scan_on_pr:
            log.info("PR scan disabled for repo", repo=repo.full_name)
            return

        # Create scan record
        scan_id = str(uuid.uuid4())
        scan = Scan(
            id=scan_id,
            repository_id=str(repo.id),
            trigger="pr",
            pr_number=pr.get("number"),
            pr_title=pr.get("title", "")[:499],
            pr_url=pr.get("html_url", ""),
            pr_author=pr.get("user", {}).get("login", ""),
            branch=pr.get("head", {}).get("ref", ""),
            base_branch=pr.get("base", {}).get("ref", ""),
            commit_sha=pr.get("head", {}).get("sha", ""),
            compare_url=payload.get("compare", ""),
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

    log.info(
        "PR scan queued",
        scan_id=scan_id,
        repo=repo_data.get("full_name"),
        pr=pr.get("number"),
    )


async def _handle_push_event(payload: dict, delivery_id: str) -> None:
    """Create a scan job for a branch push (if scan_on_push is enabled)."""
    repo_data = payload.get("repository", {})
    provider_repo_id = str(repo_data.get("id", ""))
    ref = payload.get("ref", "")  # e.g. refs/heads/main
    branch = ref.replace("refs/heads/", "")
    commit_sha = payload.get("after", "")
    commit_msg = payload.get("head_commit", {}).get("message", "")[:999]

    # Skip if this is a delete push
    if payload.get("deleted"):
        return

    async with get_db_context() as db:
        result = await db.execute(
            select(Repository).where(
                Repository.provider_repo_id == provider_repo_id,
                Repository.provider == "github",
            )
        )
        repo = result.scalar_one_or_none()

        if not repo:
            return

        if not repo.scan_enabled or not repo.scan_on_push:
            return

        # Only scan configured branches
        scan_branches = repo.scan_branches or ["main", "master", "develop"]
        if branch not in scan_branches:
            return

        scan_id = str(uuid.uuid4())
        scan = Scan(
            id=scan_id,
            repository_id=str(repo.id),
            trigger="push",
            branch=branch,
            commit_sha=commit_sha,
            commit_message=commit_msg,
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

    from app.tasks.scan_tasks import trigger_scan
    trigger_scan.delay(scan_id)

    log.info("Push scan queued", scan_id=scan_id, repo=repo_data.get("full_name"), branch=branch)


async def _handle_installation_event(payload: dict) -> None:
    """Handle app installation/uninstallation events."""
    action = payload.get("action")
    installation = payload.get("installation", {})
    installation_id = str(installation.get("id", ""))

    if action == "deleted":
        # Mark all repos from this installation as disconnected
        async with get_db_context() as db:
            result = await db.execute(
                select(Repository).where(Repository.installation_id == installation_id)
            )
            repos = result.scalars().all()
            for repo in repos:
                repo.connection_status = "disconnected"
                repo.connection_error = "GitHub App installation was removed."
                repo.webhook_active = False
            await db.commit()
        log.info("GitHub App installation removed", installation_id=installation_id)


async def _handle_installation_repos_event(payload: dict) -> None:
    """Handle repositories added/removed from an installation."""
    action = payload.get("action")
    installation = payload.get("installation", {})
    installation_id = str(installation.get("id", ""))

    if action == "removed":
        removed = payload.get("repositories_removed", [])
        async with get_db_context() as db:
            for repo_data in removed:
                provider_id = str(repo_data.get("id", ""))
                result = await db.execute(
                    select(Repository).where(
                        Repository.provider_repo_id == provider_id,
                        Repository.installation_id == installation_id,
                    )
                )
                repo = result.scalar_one_or_none()
                if repo:
                    repo.connection_status = "disconnected"
                    repo.connection_error = "Repository removed from GitHub App installation."
            await db.commit()
