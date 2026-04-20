"""
CodeSentinel — Organization & OrganizationMember Models
Multi-tenant workspace isolation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.repository import Repository
    from app.models.audit import Policy, NotificationConfig, Integration


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # Plan & limits
    plan: Mapped[str] = mapped_column(String(50), default="free")
    max_repos: Mapped[int] = mapped_column(Integer, default=5)
    max_members: Mapped[int] = mapped_column(Integer, default=3)
    max_scans_per_month: Mapped[int] = mapped_column(Integer, default=100)
    scans_this_month: Mapped[int] = mapped_column(Integer, default=0)

    # Settings
    org_settings: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    compliance_profiles: Mapped[Optional[list]] = mapped_column(JSON, default=lambda: ["soc2", "owasp"])
    ai_provider_preference: Mapped[str] = mapped_column(String(50), default="ollama")
    ai_model_preference: Mapped[Optional[str]] = mapped_column(String(100))

    # Feature flags
    auto_fix_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    secret_scanning_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sbom_export_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    pr_blocking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    primary_users: Mapped[List["User"]] = relationship("User", foreign_keys="[User.primary_org_id]", back_populates="primary_org", lazy="select")
    members: Mapped[List["OrganizationMember"]] = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan", lazy="select")
    repositories: Mapped[List["Repository"]] = relationship("Repository", back_populates="organization", cascade="all, delete-orphan", lazy="select")
    policies: Mapped[List["Policy"]] = relationship("Policy", back_populates="organization", cascade="all, delete-orphan", lazy="select")
    notification_configs: Mapped[List["NotificationConfig"]] = relationship("NotificationConfig", back_populates="organization", cascade="all, delete-orphan", lazy="select")
    integrations: Mapped[List["Integration"]] = relationship("Integration", back_populates="organization", cascade="all, delete-orphan", lazy="select")

    def __repr__(self) -> str:
        return f"<Organization {self.slug}>"


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="developer")
    invited_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="members", lazy="select")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="memberships", lazy="select")

    def __repr__(self) -> str:
        return f"<Member org={self.organization_id} user={self.user_id} role={self.role}>"
