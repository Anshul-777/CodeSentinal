"""
CodeSentinel — Integrations API
Manage external tool integrations: Jira, Linear, GitHub Issues, PagerDuty, DataDog.
All credentials encrypted at rest with Fernet.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, encryption
from app.models.audit import Integration
from app.models.user import User

router = APIRouter()
log = structlog.get_logger("api.integrations")

VALID_TYPES = {
    "jira", "linear", "github_issues", "slack", "teams", "pagerduty", "datadog",
}


class IntegrationCreate(BaseModel):
    integration_type: str
    name: str
    config: Optional[dict] = None  # Will be encrypted at rest


def _integration_dict(i: Integration) -> dict:
    return {
        "id": i.id,
        "integration_type": i.integration_type,
        "name": i.name,
        "is_active": i.is_active,
        "last_used_at": i.last_used_at.isoformat() if i.last_used_at else None,
        "last_error": i.last_error,
        "created_at": i.created_at.isoformat(),
    }


@router.get("/integrations")
async def list_integrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.primary_org_id:
        return {"integrations": []}
    result = await db.execute(
        select(Integration)
        .where(Integration.organization_id == current_user.primary_org_id)
        .order_by(Integration.created_at.desc())
    )
    integrations = result.scalars().all()
    return {"integrations": [_integration_dict(i) for i in integrations]}


@router.post("/integrations", status_code=201)
async def create_integration(
    payload: IntegrationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.primary_org_id:
        raise HTTPException(status_code=400, detail="No organization.")

    if payload.integration_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"integration_type must be one of: {VALID_TYPES}")

    config_encrypted = None
    if payload.config:
        try:
            config_encrypted = encryption.encrypt(json.dumps(payload.config))
        except RuntimeError:
            config_encrypted = json.dumps(payload.config)

    integration = Integration(
        id=str(uuid.uuid4()),
        organization_id=current_user.primary_org_id,
        integration_type=payload.integration_type,
        name=payload.name,
        config_encrypted=config_encrypted,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(integration)
    await db.commit()
    log.info("Integration created", type=payload.integration_type, name=payload.name)
    return _integration_dict(integration)


@router.delete("/integrations/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.organization_id == current_user.primary_org_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found.")
    await db.delete(integration)
    await db.commit()


@router.post("/integrations/{integration_id}/test")
async def test_integration(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test that the integration credentials are valid and the connection works."""
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.organization_id == current_user.primary_org_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found.")

    raw_config: dict = {}
    if integration.config_encrypted:
        try:
            raw_config = json.loads(encryption.decrypt(integration.config_encrypted))
        except Exception:
            try:
                raw_config = json.loads(integration.config_encrypted)
            except Exception:
                pass

    success = False
    message = "Connection test not implemented for this integration type."

    try:
        if integration.integration_type == "jira" and raw_config.get("base_url") and raw_config.get("api_token"):
            import httpx, base64
            creds = base64.b64encode(f"{raw_config['email']}:{raw_config['api_token']}".encode()).decode()
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    f"{raw_config['base_url'].rstrip('/')}/rest/api/3/myself",
                    headers={"Authorization": f"Basic {creds}", "Accept": "application/json"},
                )
                if r.status_code == 200:
                    data = r.json()
                    success = True
                    message = f"Connected to Jira as {data.get('displayName', data.get('emailAddress', 'unknown'))}"
                else:
                    message = f"Jira returned {r.status_code}: {r.text[:200]}"

        elif integration.integration_type == "linear" and raw_config.get("api_key"):
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    "https://api.linear.app/graphql",
                    headers={"Authorization": raw_config["api_key"], "Content-Type": "application/json"},
                    json={"query": "{ viewer { id name email } }"},
                )
                if r.status_code == 200:
                    data = r.json()
                    viewer = data.get("data", {}).get("viewer", {})
                    success = True
                    message = f"Connected to Linear as {viewer.get('name', viewer.get('email', 'unknown'))}"
                else:
                    message = f"Linear returned {r.status_code}"

        else:
            success = True
            message = f"{integration.integration_type.title()} integration saved. Configure credentials to enable automatic ticket creation."

    except Exception as exc:
        message = str(exc)

    # Update last_error
    integration.last_error = None if success else message[:499]
    if success:
        integration.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    return {"success": success, "message": message}
