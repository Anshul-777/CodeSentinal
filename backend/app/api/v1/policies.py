"""
CodeSentinel — Policies API
Policy-as-code: create, update, toggle, and delete security enforcement rules.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import UserRole, get_current_user, require_role
from app.models.audit import Policy
from app.models.user import User

router = APIRouter()
log = structlog.get_logger("api.policies")


class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    policy_type: str  # block_merge|require_review|create_ticket|notify|auto_fix|compliance_check
    severity_threshold: Optional[str] = "critical"  # critical|high|medium|low
    policy_config: Optional[dict] = None
    applies_to_repos: Optional[list] = None
    applies_to_branches: Optional[list] = None
    is_active: bool = True


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    severity_threshold: Optional[str] = None
    policy_config: Optional[dict] = None
    is_active: Optional[bool] = None
    applies_to_repos: Optional[list] = None
    applies_to_branches: Optional[list] = None


def _policy_dict(p: Policy) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "policy_type": p.policy_type,
        "severity_threshold": p.severity_threshold,
        "policy_config": p.policy_config,
        "is_active": p.is_active,
        "applies_to_repos": p.applies_to_repos,
        "applies_to_branches": p.applies_to_branches,
        "created_by_id": p.created_by_id,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


@router.get("/policies")
async def list_policies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.primary_org_id:
        return {"policies": []}
    result = await db.execute(
        select(Policy)
        .where(Policy.organization_id == current_user.primary_org_id)
        .order_by(Policy.created_at.desc())
    )
    policies = result.scalars().all()
    return {"policies": [_policy_dict(p) for p in policies]}


@router.post("/policies", status_code=201)
async def create_policy(
    payload: PolicyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.primary_org_id:
        raise HTTPException(status_code=400, detail="No organization found.")

    valid_types = {"block_merge", "require_review", "create_ticket", "notify", "auto_fix", "compliance_check"}
    if payload.policy_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"policy_type must be one of: {valid_types}")

    policy = Policy(
        id=str(uuid.uuid4()),
        organization_id=current_user.primary_org_id,
        name=payload.name,
        description=payload.description,
        policy_type=payload.policy_type,
        severity_threshold=payload.severity_threshold,
        policy_config=payload.policy_config,
        applies_to_repos=payload.applies_to_repos,
        applies_to_branches=payload.applies_to_branches,
        is_active=payload.is_active,
        created_by_id=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(policy)
    await db.commit()
    log.info("Policy created", name=payload.name, type=payload.policy_type, user=current_user.email)
    return _policy_dict(policy)


@router.patch("/policies/{policy_id}")
async def update_policy(
    policy_id: str,
    payload: PolicyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Policy).where(
            Policy.id == policy_id,
            Policy.organization_id == current_user.primary_org_id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found.")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(policy, field, value)
    policy.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _policy_dict(policy)


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Policy).where(
            Policy.id == policy_id,
            Policy.organization_id == current_user.primary_org_id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found.")
    await db.delete(policy)
    await db.commit()
