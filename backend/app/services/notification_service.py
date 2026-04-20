"""
CodeSentinel — Notification Service
Dispatches alerts to Slack, email, Teams, and webhooks.
Called by the scan pipeline after completion.
"""
from __future__ import annotations

import json
from typing import Optional

import httpx
import structlog

from app.core.security import encryption

log = structlog.get_logger("services.notification")


async def send_slack(webhook_url: str, text: str, blocks: Optional[list] = None) -> bool:
    """Send a Slack message via Incoming Webhook."""
    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(webhook_url, json=payload)
            return r.status_code in (200, 204)
    except Exception as exc:
        log.error("Slack notification failed", error=str(exc))
        return False


async def send_teams(webhook_url: str, title: str, text: str, color: str = "0076D7") -> bool:
    """Send a Teams message via Incoming Webhook."""
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": title,
        "sections": [{"activityTitle": title, "activityText": text}],
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(webhook_url, json=payload)
            return r.status_code in (200, 204)
    except Exception as exc:
        log.error("Teams notification failed", error=str(exc))
        return False


async def send_custom_webhook(url: str, payload: dict) -> bool:
    """POST JSON to a custom webhook endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload)
            return r.status_code in (200, 201, 204)
    except Exception as exc:
        log.error("Webhook notification failed", error=str(exc))
        return False


async def dispatch_scan_notifications(
    scan_id: str,
    org_id: str,
    risk_score: int,
    findings_critical: int,
    findings_total: int,
    merge_blocked: bool,
    repo_full_name: str,
    pr_number: Optional[int] = None,
    pr_url: Optional[str] = None,
) -> None:
    """
    Called after scan completion. Reads notification configs for the org
    and dispatches to all matching channels.
    """
    from app.core.database import get_db_context
    from app.models.audit import NotificationConfig
    from sqlalchemy import select
    from datetime import datetime, timezone

    trigger = "critical_finding" if findings_critical > 0 else "scan_complete"
    if merge_blocked:
        trigger = "merge_blocked"

    async with get_db_context() as db:
        result = await db.execute(
            select(NotificationConfig).where(
                NotificationConfig.organization_id == org_id,
                NotificationConfig.is_active == True,
            )
        )
        configs = result.scalars().all()

        for config in configs:
            triggers = config.triggers or []
            if trigger not in triggers and "scan_complete" not in triggers:
                continue

            severity_filter = config.severity_filter or []
            if severity_filter and "critical" not in severity_filter and findings_critical == 0:
                continue

            # Decrypt config
            raw_config: dict = {}
            if config.config_encrypted:
                try:
                    raw_config = json.loads(encryption.decrypt(config.config_encrypted))
                except Exception:
                    try:
                        raw_config = json.loads(config.config_encrypted)
                    except Exception:
                        continue

            # Build message
            severity_emoji = "🔴" if findings_critical > 0 else ("🟠" if risk_score >= 50 else "✅")
            blocked_str = " — ⛔ MERGE BLOCKED" if merge_blocked else ""
            title = f"{severity_emoji} CodeSentinel: {repo_full_name}{blocked_str}"
            body = (
                f"Risk Score: *{risk_score}/100*\n"
                f"Findings: {findings_total} total, {findings_critical} critical\n"
                f"Repository: `{repo_full_name}`"
            )
            if pr_url:
                body += f"\nPR: {pr_url}"

            sent = False
            if config.channel == "slack" and raw_config.get("webhook_url"):
                sent = await send_slack(raw_config["webhook_url"], f"{title}\n{body}")
            elif config.channel == "teams" and raw_config.get("webhook_url"):
                sent = await send_teams(raw_config["webhook_url"], title, body, "FF0000" if findings_critical > 0 else "0076D7")
            elif config.channel == "webhook" and raw_config.get("url"):
                sent = await send_custom_webhook(raw_config["url"], {
                    "source": "CodeSentinel",
                    "trigger": trigger,
                    "scan_id": scan_id,
                    "repository": repo_full_name,
                    "risk_score": risk_score,
                    "findings_critical": findings_critical,
                    "findings_total": findings_total,
                    "merge_blocked": merge_blocked,
                    "pr_url": pr_url,
                })

            if sent:
                config.last_sent_at = datetime.now(timezone.utc)
                log.info("Notification sent", channel=config.channel, org=org_id, trigger=trigger)

        await db.commit()
