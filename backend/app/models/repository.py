"""
CodeSentinel — Repository Model
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.scan import Scan


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Provider info
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # github|gitlab|bitbucket
    provider_repo_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    url: Mapped[Optional[str]] = mapped_column(String(500))
    clone_url: Mapped[Optional[str]] = mapped_column(String(500))
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    language: Mapped[Optional[str]] = mapped_column(String(50))
    is_private: Mapped[bool] = mapped_column(Boolean, default=True)
    stars_count: Mapped[int] = mapped_column(Integer, default=0)

    # GitHub App install context
    installation_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    access_token_encrypted: Mapped[Optional[str]] = mapped_column(String(2000))
    access_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Webhook
    webhook_id: Mapped[Optional[str]] = mapped_column(String(100))
    webhook_secret_encrypted: Mapped[Optional[str]] = mapped_column(String(500))
    webhook_active: Mapped[bool] = mapped_column(Boolean, default=False)

    # Permissions
    has_read_access: Mapped[bool] = mapped_column(Boolean, default=True)
    has_write_access: Mapped[bool] = mapped_column(Boolean, default=False)
    has_check_access: Mapped[bool] = mapped_column(Boolean, default=False)
    can_create_pr: Mapped[bool] = mapped_column(Boolean, default=False)
    can_post_comments: Mapped[bool] = mapped_column(Boolean, default=False)

    # Scan config
    scan_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    scan_on_pr: Mapped[bool] = mapped_column(Boolean, default=True)
    scan_on_push: Mapped[bool] = mapped_column(Boolean, default=False)
    scan_branches: Mapped[Optional[list]] = mapped_column(JSON, default=lambda: ["main", "master", "develop"])

    # Auto-fix config
    auto_fix_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_fix_mode: Mapped[str] = mapped_column(String(50), default="suggest")  # suggest|auto_commit|auto_pr
    auto_fix_branch_prefix: Mapped[str] = mapped_column(String(50), default="codesentinel/fix")

    # Blocking rules
    block_on_critical: Mapped[bool] = mapped_column(Boolean, default=True)
    block_on_high: Mapped[bool] = mapped_column(Boolean, default=False)
    block_on_secret: Mapped[bool] = mapped_column(Boolean, default=True)
    require_review_threshold: Mapped[str] = mapped_column(String(20), default="high")

    # Compliance
    compliance_profiles: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    codeowners: Mapped[Optional[dict]] = mapped_column(JSON)

    # Stats (cached)
    total_scans: Mapped[int] = mapped_column(Integer, default=0)
    total_findings: Mapped[int] = mapped_column(Integer, default=0)
    open_findings: Mapped[int] = mapped_column(Integer, default=0)
    last_scan_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_scan_risk_score: Mapped[Optional[int]] = mapped_column(Integer)

    # Connection state
    connection_status: Mapped[str] = mapped_column(String(20), default="connected")
    connection_error: Mapped[Optional[str]] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="repositories", lazy="select")
    scans: Mapped[List["Scan"]] = relationship("Scan", back_populates="repository", cascade="all, delete-orphan", lazy="dynamic", order_by="Scan.created_at.desc()")

    def __repr__(self) -> str:
        return f"<Repository {self.full_name}>"
