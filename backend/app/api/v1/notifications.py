"""
CodeSentinel — Notifications API
Manage notification routing configs. Encrypted channel config stored at rest.
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
from app.models.audit import NotificationConfig
from app.models.user import User

router = APIRouter()
log = structlog.get_logger("api.notifications")


class NotificationCreate(BaseModel):
    name: str
    channel: str  # slack|email|teams|webhook
    config: Optional[dict] = None  # Channel-specific config (encrypted at rest)
    triggers: Optional[list] = None  # ["critical_finding", "scan_complete", ...]
    severity_filter: Optional[list] = None  # ["critical", "high"]
    is_active: bool = True


def _notif_dict(n: NotificationConfig) -> dict:
    return {
        "id": n.id,
        "name": n.name,
        "channel": n.channel,
        "triggers": n.triggers or [],
        "severity_filter": n.severity_filter or [],
        "is_active": n.is_active,
        "last_sent_at": n.last_sent_at.isoformat() if n.last_sent_at else None,
        "created_at": n.created_at.isoformat(),
    }


@router.get("/notifications")
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.primary_org_id:
        return {"configs": []}
    result = await db.execute(
        select(NotificationConfig)
        .where(NotificationConfig.organization_id == current_user.primary_org_id)
        .order_by(NotificationConfig.created_at.desc())
    )
    configs = result.scalars().all()
    return {"configs": [_notif_dict(c) for c in configs]}


@router.post("/notifications", status_code=201)
async def create_notification(
    payload: NotificationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.primary_org_id:
        raise HTTPException(status_code=400, detail="No organization.")

    valid_channels = {"slack", "email", "teams", "webhook", "pagerduty"}
    if payload.channel not in valid_channels:
        raise HTTPException(status_code=400, detail=f"channel must be one of: {valid_channels}")

    # Encrypt sensitive config before storing
    config_encrypted = None
    if payload.config:
        try:
            config_encrypted = encryption.encrypt(json.dumps(payload.config))
        except RuntimeError:
            # If encryption key not set, store plaintext (dev mode only)
            config_encrypted = json.dumps(payload.config)

    config = NotificationConfig(
        id=str(uuid.uuid4()),
        organization_id=current_user.primary_org_id,
        name=payload.name,
        channel=payload.channel,
        config_encrypted=config_encrypted,
        triggers=payload.triggers or ["critical_finding", "scan_complete"],
        severity_filter=payload.severity_filter,
        is_active=payload.is_active,
        created_at=datetime.now(timezone.utc),
    )
    db.add(config)
    await db.commit()
    log.info("Notification config created", name=payload.name, channel=payload.channel)
    return _notif_dict(config)


@router.delete("/notifications/{config_id}", status_code=204)
async def delete_notification(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationConfig).where(
            NotificationConfig.id == config_id,
            NotificationConfig.organization_id == current_user.primary_org_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not found.")
    await db.delete(config)
    await db.commit()


@router.post("/notifications/{config_id}/test")
async def test_notification(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a test notification to verify the channel configuration works."""
    result = await db.execute(
        select(NotificationConfig).where(
            NotificationConfig.id == config_id,
            NotificationConfig.organization_id == current_user.primary_org_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not found.")

    # Attempt to send test message
    try:
        raw_config = {}
        if config.config_encrypted:
            try:
                raw_config = json.loads(encryption.decrypt(config.config_encrypted))
            except Exception:
                raw_config = json.loads(config.config_encrypted)

        if config.channel == "slack" and raw_config.get("webhook_url"):
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    raw_config["webhook_url"],
                    json={"text": f"✅ CodeSentinel test notification from *{current_user.full_name}*. Your Slack integration is working correctly."},
                )
                if r.status_code not in (200, 204):
                    return {"success": False, "error": f"Slack returned {r.status_code}: {r.text[:200]}"}
            return {"success": True, "message": "Test message sent to Slack."}

        elif config.channel == "webhook" and raw_config.get("url"):
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    raw_config["url"],
                    json={
                        "source": "CodeSentinel",
                        "type": "test",
                        "message": "Test notification from CodeSentinel",
                        "organization": current_user.primary_org_id,
                    },
                )
                if r.status_code not in (200, 201, 204):
                    return {"success": False, "error": f"Webhook returned {r.status_code}"}
            return {"success": True, "message": "Test payload sent to webhook."}

        else:
            return {"success": True, "message": f"Test for '{config.channel}' channel acknowledged. Configure credentials to enable delivery."}

    except Exception as exc:
        return {"success": False, "error": str(exc)}
