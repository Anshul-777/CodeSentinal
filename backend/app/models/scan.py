"""
CodeSentinel — Scan Model
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.finding import Finding
    from app.models.fix import Fix


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)

    # Trigger context
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)  # pr|push|manual|scheduled
    pr_number: Mapped[Optional[int]] = mapped_column(Integer)
    pr_title: Mapped[Optional[str]] = mapped_column(String(500))
    pr_url: Mapped[Optional[str]] = mapped_column(String(500))
    pr_author: Mapped[Optional[str]] = mapped_column(String(200))
    branch: Mapped[Optional[str]] = mapped_column(String(200))
    base_branch: Mapped[Optional[str]] = mapped_column(String(200))
    commit_sha: Mapped[Optional[str]] = mapped_column(String(40))
    commit_message: Mapped[Optional[str]] = mapped_column(String(1000))
    compare_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Scope
    files_changed: Mapped[Optional[list]] = mapped_column(JSON)
    files_scanned_count: Mapped[int] = mapped_column(Integer, default=0)
    lines_scanned: Mapped[int] = mapped_column(Integer, default=0)
    scan_scope: Mapped[str] = mapped_column(String(50), default="diff")  # diff|full

    # Status
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", index=True)
    # queued|running|completed|failed|cancelled|blocked

    # Per-agent state
    agent_states: Mapped[Optional[dict]] = mapped_column(JSON, default=lambda: {
        "static": "waiting", "dependency": "waiting",
        "business_logic": "waiting", "autofix": "waiting", "compliance": "waiting",
    })
    agent_results: Mapped[Optional[dict]] = mapped_column(JSON)
    agent_errors: Mapped[Optional[dict]] = mapped_column(JSON)
    agent_durations: Mapped[Optional[dict]] = mapped_column(JSON)

    # Risk summary
    risk_score: Mapped[Optional[int]] = mapped_column(Integer)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20))
    findings_total: Mapped[int] = mapped_column(Integer, default=0)
    findings_critical: Mapped[int] = mapped_column(Integer, default=0)
    findings_high: Mapped[int] = mapped_column(Integer, default=0)
    findings_medium: Mapped[int] = mapped_column(Integer, default=0)
    findings_low: Mapped[int] = mapped_column(Integer, default=0)
    findings_info: Mapped[int] = mapped_column(Integer, default=0)
    secrets_found: Mapped[int] = mapped_column(Integer, default=0)
    dependencies_vulnerable: Mapped[int] = mapped_column(Integer, default=0)
    fixes_available: Mapped[int] = mapped_column(Integer, default=0)
    fixes_applied: Mapped[int] = mapped_column(Integer, default=0)

    # AI used
    ai_provider: Mapped[Optional[str]] = mapped_column(String(50))
    ai_model: Mapped[Optional[str]] = mapped_column(String(100))
    ai_tokens_used: Mapped[int] = mapped_column(Integer, default=0)

    # Compliance
    compliance_results: Mapped[Optional[dict]] = mapped_column(JSON)

    # Merge gate
    merge_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    merge_block_reason: Mapped[Optional[str]] = mapped_column(String(500))
    check_run_id: Mapped[Optional[str]] = mapped_column(String(100))
    check_run_url: Mapped[Optional[str]] = mapped_column(String(500))
    pr_review_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Celery
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Timing
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="scans", lazy="select")
    findings: Mapped[List["Finding"]] = relationship("Finding", back_populates="scan", cascade="all, delete-orphan", lazy="dynamic")
    fixes: Mapped[List["Fix"]] = relationship("Fix", back_populates="scan", cascade="all, delete-orphan", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Scan {self.id} status={self.status} risk={self.risk_score}>"
