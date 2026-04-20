"""
CodeSentinel — Settings API
User profile update, organization settings, GitHub App install URL generation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.organization import Organization
from app.models.user import User

router = APIRouter()
log = structlog.get_logger("api.settings")


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    github_username: Optional[str] = None
    phone: Optional[str] = None
    user_timezone: Optional[str] = None
    notify_email: Optional[bool] = None
    notify_slack: Optional[bool] = None
    notify_critical_only: Optional[bool] = None


class OrgSettingsUpdate(BaseModel):
    auto_fix_enabled: Optional[bool] = None
    secret_scanning_enabled: Optional[bool] = None
    sbom_export_enabled: Optional[bool] = None
    pr_blocking_enabled: Optional[bool] = None
    compliance_profiles: Optional[list] = None
    ai_provider_preference: Optional[str] = None
    ai_model_preference: Optional[str] = None


def _user_dict(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name,
        "job_title": u.job_title, "company": u.company,
        "github_username": u.github_username, "phone": u.phone,
        "avatar_url": u.avatar_url, "user_timezone": u.user_timezone,
        "notify_email": u.notify_email, "notify_slack": u.notify_slack,
        "notify_critical_only": u.notify_critical_only,
        "is_test_user": u.is_test_user, "tour_completed": u.tour_completed,
        "tour_step": u.tour_step, "api_key_prefix": u.api_key_prefix,
        "created_at": u.created_at.isoformat(),
    }


@router.patch("/settings/profile")
async def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _user_dict(user)


@router.patch("/settings/organization")
async def update_org_settings(
    payload: OrgSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.primary_org_id:
        raise HTTPException(status_code=400, detail="No organization.")

    result = await db.execute(select(Organization).where(Organization.id == current_user.primary_org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(org, field, value)
    org.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {
        "id": org.id, "name": org.name, "slug": org.slug, "plan": org.plan,
        "auto_fix_enabled": org.auto_fix_enabled,
        "secret_scanning_enabled": org.secret_scanning_enabled,
        "sbom_export_enabled": org.sbom_export_enabled,
        "pr_blocking_enabled": org.pr_blocking_enabled,
        "compliance_profiles": org.compliance_profiles,
        "ai_provider_preference": org.ai_provider_preference,
        "ai_model_preference": org.ai_model_preference,
    }


@router.get("/settings/github-app-url")
async def get_github_app_install_url(
    current_user: User = Depends(get_current_user),
):
    """Return the GitHub App installation URL for the connect flow."""
    if not settings.GITHUB_APP_NAME:
        return {
            "url": None,
            "configured": False,
            "message": "GitHub App not configured. Set GITHUB_APP_NAME in .env",
        }
    url = f"https://github.com/apps/{settings.GITHUB_APP_NAME}/installations/new"
    return {
        "url": url,
        "configured": settings.github_configured,
        "app_name": settings.GITHUB_APP_NAME,
    }
