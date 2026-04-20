"""
CodeSentinel — Issue Tracker Integration Service
Creates tickets in Jira, Linear, and GitHub Issues for findings.
"""
from __future__ import annotations

import json
from typing import Optional

import httpx
import structlog

from app.core.security import encryption

log = structlog.get_logger("services.tickets")


async def create_jira_issue(
    base_url: str,
    email: str,
    api_token: str,
    project_key: str,
    summary: str,
    description: str,
    priority: str = "High",
    labels: Optional[list] = None,
) -> Optional[str]:
    """Create a Jira issue. Returns the issue key (e.g., SEC-123) or None."""
    import base64
    credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()

    priority_map = {"critical": "Highest", "high": "High", "medium": "Medium", "low": "Low"}
    jira_priority = priority_map.get(priority.lower(), "High")

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary[:254],
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": description[:5000]}]}
                ],
            },
            "issuetype": {"name": "Bug"},
            "priority": {"name": jira_priority},
            "labels": ["codesentinel", "security"] + (labels or []),
        }
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{base_url.rstrip('/')}/rest/api/3/issue",
                headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/json"},
                json=payload,
            )
            if r.status_code == 201:
                data = r.json()
                issue_key = data.get("key")
                log.info("Jira issue created", key=issue_key)
                return issue_key
            else:
                log.error("Jira issue creation failed", status=r.status_code, body=r.text[:500])
                return None
    except Exception as exc:
        log.error("Jira request failed", error=str(exc))
        return None


async def create_linear_issue(
    api_key: str,
    team_id: str,
    title: str,
    description: str,
    priority: int = 2,  # 1=urgent, 2=high, 3=medium, 4=low
) -> Optional[str]:
    """Create a Linear issue. Returns the issue ID or None."""
    mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
        issueCreate(input: $input) {
            success
            issue { id identifier url }
        }
    }
    """
    variables = {
        "input": {
            "teamId": team_id,
            "title": title[:255],
            "description": description[:10000],
            "priority": priority,
            "labelIds": [],
        }
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://api.linear.app/graphql",
                headers={"Authorization": api_key, "Content-Type": "application/json"},
                json={"query": mutation, "variables": variables},
            )
            if r.status_code == 200:
                data = r.json()
                issue = data.get("data", {}).get("issueCreate", {}).get("issue")
                if issue:
                    log.info("Linear issue created", id=issue["identifier"])
                    return issue["identifier"]
            log.error("Linear issue creation failed", status=r.status_code)
            return None
    except Exception as exc:
        log.error("Linear request failed", error=str(exc))
        return None


async def create_ticket_for_finding(
    finding_id: str,
    org_id: str,
) -> Optional[str]:
    """
    Look up the org's integrations and create a ticket for the given finding.
    Returns the ticket identifier (Jira key or Linear ID) if successful.
    """
    from app.core.database import get_db_context
    from app.models.audit import Integration
    from app.models.finding import Finding
    from sqlalchemy import select, or_

    async with get_db_context() as db:
        # Load the finding
        f_result = await db.execute(select(Finding).where(Finding.id == finding_id))
        finding = f_result.scalar_one_or_none()
        if not finding:
            return None

        # Load integrations for this org
        i_result = await db.execute(
            select(Integration).where(
                Integration.organization_id == org_id,
                Integration.is_active == True,
                Integration.integration_type.in_(["jira", "linear"]),
            )
        )
        integrations = i_result.scalars().all()

        if not integrations:
            return None

        # Build ticket content
        severity_str = finding.severity.upper()
        title = f"[{severity_str}] {finding.title}"
        desc_parts = [
            f"**Severity:** {severity_str}",
            f"**Rule:** {finding.rule_id or 'N/A'}",
            f"**File:** {finding.file_path or 'N/A'}:{finding.line_start or ''}",
            "",
            f"**Description:**\n{finding.description or ''}",
            "",
            f"**Why this was flagged:**\n{finding.why_flagged or ''}",
            "",
            f"**Business Risk:**\n{finding.business_risk or ''}",
            "",
            f"**Recommendation:**\n{finding.recommendation or ''}",
            "",
            f"Source: CodeSentinel automated security scan — Finding ID: {finding_id}",
        ]
        description = "\n".join(desc_parts)

        for integration in integrations:
            raw_config: dict = {}
            if integration.config_encrypted:
                try:
                    raw_config = json.loads(encryption.decrypt(integration.config_encrypted))
                except Exception:
                    try:
                        raw_config = json.loads(integration.config_encrypted)
                    except Exception:
                        continue

            if integration.integration_type == "jira":
                ticket_id = await create_jira_issue(
                    base_url=raw_config.get("base_url", ""),
                    email=raw_config.get("email", ""),
                    api_token=raw_config.get("api_token", ""),
                    project_key=raw_config.get("project_key", "SEC"),
                    summary=title,
                    description=description,
                    priority=finding.severity,
                )
                if ticket_id:
                    return ticket_id

            elif integration.integration_type == "linear":
                prio_map = {"critical": 1, "high": 2, "medium": 3, "low": 4}
                ticket_id = await create_linear_issue(
                    api_key=raw_config.get("api_key", ""),
                    team_id=raw_config.get("team_id", ""),
                    title=title,
                    description=description,
                    priority=prio_map.get(finding.severity, 2),
                )
                if ticket_id:
                    return ticket_id

    return None
