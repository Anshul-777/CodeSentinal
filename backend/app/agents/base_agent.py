"""
CodeSentinel — Base Agent
Abstract class every security agent extends.
Handles timing, structured logging, state persistence, and error capture.
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import structlog

from app.core.database import get_db_context

log = structlog.get_logger("agents")


@dataclass
class AgentContext:
    """All inputs an agent receives when invoked for a scan."""
    scan_id: str
    repository_id: str
    organization_id: str
    # Diff content or full file list
    diff_content: Optional[str] = None
    changed_files: list[dict] = field(default_factory=list)
    # File contents keyed by path
    file_contents: dict[str, str] = field(default_factory=dict)
    # Dependency manifests keyed by path
    manifests: dict[str, str] = field(default_factory=dict)
    # Repo full_name e.g. "org/repo"
    repo_full_name: str = ""
    repo_default_branch: str = "main"
    repo_language: Optional[str] = None
    # Compliance profiles enabled for this repo
    compliance_profiles: list[str] = field(default_factory=list)
    # AI provider/model preference from org settings
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    # Results from other agents (for the auto-fix agent, passed findings)
    upstream_results: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Structured output from any agent."""
    agent_name: str
    success: bool
    findings: list[dict] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    error_detail: Optional[str] = None
    duration_seconds: float = 0.0
    tokens_used: int = 0
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None


class BaseAgent(ABC):
    """
    Abstract base class for all CodeSentinel security agents.

    Subclasses must implement `run()`. This base class handles:
    - Timing and performance tracking
    - Structured logging with scan context
    - Exception handling so one agent failure doesn't break the pipeline
    - Persisting agent_states to the Scan row in real time
    """

    name: str = "base"
    display_name: str = "Base Agent"

    async def execute(self, ctx: AgentContext) -> AgentResult:
        """Execute the agent with full error handling and state tracking."""
        start = time.perf_counter()
        log.info("Agent starting", agent=self.name, scan_id=ctx.scan_id)

        # Update scan state to running
        await self._update_scan_agent_state(ctx.scan_id, self.name, "running")

        try:
            result = await self.run(ctx)
            result.duration_seconds = time.perf_counter() - start

            log.info(
                "Agent completed",
                agent=self.name,
                scan_id=ctx.scan_id,
                findings=len(result.findings),
                duration=round(result.duration_seconds, 2),
                tokens=result.tokens_used,
            )
            await self._update_scan_agent_state(ctx.scan_id, self.name, "completed")
            return result

        except Exception as exc:
            duration = time.perf_counter() - start
            log.error(
                "Agent failed",
                agent=self.name,
                scan_id=ctx.scan_id,
                error=str(exc),
                duration=round(duration, 2),
                exc_info=True,
            )
            await self._update_scan_agent_state(ctx.scan_id, self.name, "failed", error=str(exc))
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(exc),
                error_detail=repr(exc),
                duration_seconds=duration,
            )

    @abstractmethod
    async def run(self, ctx: AgentContext) -> AgentResult:
        """Implement actual agent logic here."""
        ...

    async def _update_scan_agent_state(
        self,
        scan_id: str,
        agent_name: str,
        state: str,
        error: Optional[str] = None,
    ) -> None:
        """Persist agent state to the database so the dashboard can poll it."""
        try:
            from sqlalchemy import select
            from app.models.scan import Scan
            async with get_db_context() as db:
                result = await db.execute(select(Scan).where(Scan.id == scan_id))
                scan = result.scalar_one_or_none()
                if scan:
                    states = dict(scan.agent_states or {})
                    states[agent_name] = state
                    scan.agent_states = states
                    if error:
                        errors = dict(scan.agent_errors or {})
                        errors[agent_name] = error
                        scan.agent_errors = errors
                    await db.commit()
        except Exception as exc:
            # Don't let state persistence failure crash the agent
            log.warning("Failed to update agent state in DB", agent=agent_name, error=str(exc))
