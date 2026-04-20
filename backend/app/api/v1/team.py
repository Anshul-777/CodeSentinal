"""
CodeSentinel — Team Management API
Invite, update roles, and remove organization members.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import UserRole, get_current_user, has_permission
from app.models.organization import Organization, OrganizationMember
from app.models.user import User

router = APIRouter()
log = structlog.get_logger("api.team")

VALID_ROLES = {"admin", "analyst", "developer", "viewer"}


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "developer"


class RoleUpdateRequest(BaseModel):
    role: str


def _member_dict(m: OrganizationMember, user: Optional[User] = None) -> dict:
    return {
        "id": m.id,
        "organization_id": m.organization_id,
        "user_id": m.user_id,
        "role": m.role,
        "is_active": m.is_active,
        "accepted_at": m.accepted_at.isoformat() if m.accepted_at else None,
        "created_at": m.created_at.isoformat(),
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "job_title": user.job_title,
            "avatar_url": user.avatar_url,
        } if user else None,
    }


@router.get("/team")
async def list_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.primary_org_id:
        return {"members": []}

    result = await db.execute(
        select(OrganizationMember, User)
        .join(User, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.organization_id == current_user.primary_org_id)
        .order_by(OrganizationMember.created_at.asc())
    )
    rows = result.all()
    return {"members": [_member_dict(m, u) for m, u in rows]}


@router.post("/team/invite", status_code=201)
async def invite_member(
    payload: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Invite a user by email. If they have an account, adds them directly. Otherwise creates a pending invite."""
    if not current_user.primary_org_id:
        raise HTTPException(status_code=400, detail="No organization.")

    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {VALID_ROLES}")

    # Check if user already exists
    user_result = await db.execute(select(User).where(User.email == payload.email.lower()))
    invited_user = user_result.scalar_one_or_none()

    if not invited_user:
        # Create a placeholder user account (they'll set password on first login)
        invited_user = User(
            id=str(uuid.uuid4()),
            email=payload.email.lower(),
            hashed_password="",  # No password — invite flow
            full_name=payload.email.split("@")[0].replace(".", " ").title(),
            is_active=False,  # Inactive until they accept
            is_verified=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(invited_user)

    # Check not already a member
    existing = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == current_user.primary_org_id,
            OrganizationMember.user_id == invited_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This user is already a member.")

    membership = OrganizationMember(
        id=str(uuid.uuid4()),
        organization_id=current_user.primary_org_id,
        user_id=invited_user.id,
        role=payload.role,
        invited_by_id=current_user.id,
        is_active=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(membership)
    await db.commit()

    log.info("Member invited", email=payload.email, role=payload.role, inviter=current_user.email)
    return {"message": f"Invitation sent to {payload.email}", "role": payload.role}


@router.patch("/team/{member_id}")
async def update_member_role(
    member_id: str,
    payload: RoleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {VALID_ROLES}")

    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == current_user.primary_org_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")
    if member.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot change the owner's role.")

    member.role = payload.role
    await db.commit()
    return {"message": "Role updated.", "role": payload.role}


@router.delete("/team/{member_id}", status_code=204)
async def remove_member(
    member_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == current_user.primary_org_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")
    if member.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot remove the organization owner.")
    if member.user_id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot remove yourself.")

    await db.delete(member)
    await db.commit()
