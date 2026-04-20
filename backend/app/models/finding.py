"""
CodeSentinel — Finding Model
Every finding has a complete evidence trail: location, severity, business risk,
compliance impact, and "why this was flagged" explanation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.scan import Scan
    from app.models.fix import Fix


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)

    # Source agent
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # static|dependency|business_logic|compliance|secret

    # Rule/CVE identity
    rule_id: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    cve_id: Mapped[Optional[str]] = mapped_column(String(50))
    cwe_id: Mapped[Optional[str]] = mapped_column(String(50))
    owasp_category: Mapped[Optional[str]] = mapped_column(String(100))

    # Description — every field must be filled by the agent, never empty
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    business_risk: Mapped[Optional[str]] = mapped_column(Text)
    # "Why was this flagged?" — the core user-facing explanation
    why_flagged: Mapped[Optional[str]] = mapped_column(Text)
    recommendation: Mapped[Optional[str]] = mapped_column(Text)
    references: Mapped[Optional[list]] = mapped_column(JSON)

    # Location
    file_path: Mapped[Optional[str]] = mapped_column(String(1000))
    line_start: Mapped[Optional[int]] = mapped_column(Integer)
    line_end: Mapped[Optional[int]] = mapped_column(Integer)
    column_start: Mapped[Optional[int]] = mapped_column(Integer)
    code_snippet: Mapped[Optional[str]] = mapped_column(Text)
    code_context: Mapped[Optional[str]] = mapped_column(Text)  # ±5 lines

    # Severity
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    cvss_score: Mapped[Optional[float]] = mapped_column(Float)
    cvss_vector: Mapped[Optional[str]] = mapped_column(String(100))
    confidence: Mapped[str] = mapped_column(String(20), default="high")  # high|medium|low

    # Category (injection|xss|auth|crypto|secrets|license|compliance|logic|config)
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    # Compliance impact
    compliance_frameworks: Mapped[Optional[list]] = mapped_column(JSON)
    compliance_details: Mapped[Optional[dict]] = mapped_column(JSON)

    # Dependency-specific fields
    dependency_name: Mapped[Optional[str]] = mapped_column(String(255))
    dependency_version: Mapped[Optional[str]] = mapped_column(String(100))
    dependency_fixed_version: Mapped[Optional[str]] = mapped_column(String(100))
    dependency_ecosystem: Mapped[Optional[str]] = mapped_column(String(50))

    # Secret-specific fields
    secret_type: Mapped[Optional[str]] = mapped_column(String(100))
    secret_verified: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Status lifecycle
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open", index=True)
    # open|fixed|ignored|false_positive|accepted_risk

    # False positive feedback
    is_false_positive: Mapped[bool] = mapped_column(Boolean, default=False)
    false_positive_reason: Mapped[Optional[str]] = mapped_column(String(500))
    false_positive_reported_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    false_positive_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Fix availability
    fix_available: Mapped[bool] = mapped_column(Boolean, default=False)
    fix_complexity: Mapped[Optional[str]] = mapped_column(String(20))  # trivial|simple|moderate|complex|manual

    # Dedup fingerprint — SHA256(rule_id + file_path + line + code_hash)
    fingerprint: Mapped[Optional[str]] = mapped_column(String(64), index=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    scan: Mapped["Scan"] = relationship("Scan", back_populates="findings", lazy="select")
    fixes: Mapped[List["Fix"]] = relationship("Fix", back_populates="finding", cascade="all, delete-orphan", lazy="select")

    def __repr__(self) -> str:
        return f"<Finding {self.severity} {self.rule_id} {self.file_path}:{self.line_start}>"
