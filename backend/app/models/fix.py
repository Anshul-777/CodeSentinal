"""
CodeSentinel — Fix Model
Full auto-fix lifecycle: patch generation → sandbox test → verify → apply → confirm.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.finding import Finding
    from app.models.scan import Scan


class Fix(Base):
    __tablename__ = "fixes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id: Mapped[str] = mapped_column(String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)

    # Fix type
    fix_type: Mapped[str] = mapped_column(String(50), nullable=False)  # automated|suggested|manual
    fix_strategy: Mapped[Optional[str]] = mapped_column(String(100))

    # Patch content
    file_path: Mapped[Optional[str]] = mapped_column(String(1000))
    original_code: Mapped[Optional[str]] = mapped_column(Text)
    fixed_code: Mapped[Optional[str]] = mapped_column(Text)
    diff_patch: Mapped[Optional[str]] = mapped_column(Text)  # unified diff
    diff_stats: Mapped[Optional[dict]] = mapped_column(JSON)

    # Explanations
    description: Mapped[Optional[str]] = mapped_column(Text)
    why_safe: Mapped[Optional[str]] = mapped_column(Text)
    step_by_step: Mapped[Optional[str]] = mapped_column(Text)

    # Sandbox
    sandbox_status: Mapped[str] = mapped_column(String(30), default="pending")
    # pending|running|passed|failed|skipped
    sandbox_test_output: Mapped[Optional[str]] = mapped_column(Text)
    sandbox_lint_output: Mapped[Optional[str]] = mapped_column(Text)
    sandbox_duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    sandbox_checks_passed: Mapped[Optional[list]] = mapped_column(JSON)
    sandbox_checks_failed: Mapped[Optional[list]] = mapped_column(JSON)
    tests_passed: Mapped[Optional[int]] = mapped_column(Integer)
    tests_failed: Mapped[Optional[int]] = mapped_column(Integer)
    tests_run: Mapped[Optional[int]] = mapped_column(Integer)

    # Application status
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    # pending|sandbox_testing|verified|applying|applied|rejected|user_rejected

    # Repo application
    fix_branch: Mapped[Optional[str]] = mapped_column(String(200))
    fix_commit_sha: Mapped[Optional[str]] = mapped_column(String(40))
    fix_pr_number: Mapped[Optional[int]] = mapped_column(Integer)
    fix_pr_url: Mapped[Optional[str]] = mapped_column(String(500))
    applied_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    application_error: Mapped[Optional[str]] = mapped_column(String(1000))

    # AI model used
    ai_provider: Mapped[Optional[str]] = mapped_column(String(50))
    ai_model: Mapped[Optional[str]] = mapped_column(String(100))
    ai_prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    ai_completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)

    # Verification
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_method: Mapped[Optional[str]] = mapped_column(String(100))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    finding: Mapped["Finding"] = relationship("Finding", back_populates="fixes", lazy="select")
    scan: Mapped["Scan"] = relationship("Scan", back_populates="fixes", lazy="select")

    def __repr__(self) -> str:
        return f"<Fix {self.id} status={self.status} sandbox={self.sandbox_status}>"
