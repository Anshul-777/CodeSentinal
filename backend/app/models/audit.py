"""
CodeSentinel — Audit Log, Policy, NotificationConfig, Integration Models
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.organization import Organization


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="SET NULL"), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255))
    actor_role: Mapped[Optional[str]] = mapped_column(String(50))

    # Action
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100))
    resource_name: Mapped[Optional[str]] = mapped_column(String(500))

    # Context
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    old_value: Mapped[Optional[dict]] = mapped_column(JSON)
    new_value: Mapped[Optional[dict]] = mapped_column(JSON)
    result: Mapped[str] = mapped_column(String(20), default="success")  # success|failure|error
    error_message: Mapped[Optional[str]] = mapped_column(String(500))

    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    request_id: Mapped[Optional[str]] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id], back_populates="audit_logs", lazy="select")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.actor_email}>"


class Policy(Base):
    """Policy-as-code rules that enforce security thresholds per org."""
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    policy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # block_merge|require_review|create_ticket|notify|auto_fix|compliance_check
    severity_threshold: Mapped[Optional[str]] = mapped_column(String(20))
    policy_config: Mapped[Optional[dict]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    applies_to_repos: Mapped[Optional[list]] = mapped_column(JSON)
    applies_to_branches: Mapped[Optional[list]] = mapped_column(JSON)
    created_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="policies", lazy="select")

    def __repr__(self) -> str:
        return f"<Policy {self.name} type={self.policy_type}>"


class NotificationConfig(Base):
    """Notification routing for alerts, scan results, and weekly digests."""
    __tablename__ = "notification_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)  # slack|email|teams|webhook
    config_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    triggers: Mapped[Optional[list]] = mapped_column(JSON)
    severity_filter: Mapped[Optional[list]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="notification_configs", lazy="select")

    def __repr__(self) -> str:
        return f"<NotificationConfig {self.channel} {self.name}>"


class Integration(Base):
    """External integrations: Jira, Linear, Slack, DataDog, etc."""
    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # jira|linear|github_issues|slack|teams|pagerduty|datadog
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    config_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="integrations", lazy="select")

    def __repr__(self) -> str:
        return f"<Integration {self.integration_type} {self.name}>"
