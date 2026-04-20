"""Initial schema — all CodeSentinel tables

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("job_title", sa.String(255)),
        sa.Column("company", sa.String(255)),
        sa.Column("github_username", sa.String(100)),
        sa.Column("phone", sa.String(50)),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("user_timezone", sa.String(100), server_default="UTC"),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_test_user", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_superuser", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("primary_org_id", sa.String(36)),
        sa.Column("api_key_hash", sa.String(64)),
        sa.Column("api_key_prefix", sa.String(12)),
        sa.Column("notify_email", sa.Boolean(), server_default="true"),
        sa.Column("notify_slack", sa.Boolean(), server_default="false"),
        sa.Column("notify_critical_only", sa.Boolean(), server_default="false"),
        sa.Column("tour_completed", sa.Boolean(), server_default="false"),
        sa.Column("tour_step", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_ip", sa.String(45)),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── organizations ─────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("website", sa.String(255)),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("max_repos", sa.Integer(), server_default="5"),
        sa.Column("max_members", sa.Integer(), server_default="3"),
        sa.Column("max_scans_per_month", sa.Integer(), server_default="100"),
        sa.Column("scans_this_month", sa.Integer(), server_default="0"),
        sa.Column("org_settings", postgresql.JSON()),
        sa.Column("compliance_profiles", postgresql.JSON()),
        sa.Column("ai_provider_preference", sa.String(50), server_default="ollama"),
        sa.Column("ai_model_preference", sa.String(100)),
        sa.Column("auto_fix_enabled", sa.Boolean(), server_default="false"),
        sa.Column("secret_scanning_enabled", sa.Boolean(), server_default="true"),
        sa.Column("sbom_export_enabled", sa.Boolean(), server_default="true"),
        sa.Column("pr_blocking_enabled", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # Add FK from users.primary_org_id → organizations.id
    op.create_foreign_key("fk_users_primary_org", "users", "organizations", ["primary_org_id"], ["id"], ondelete="SET NULL")

    # ── organization_members ──────────────────────────────────────
    op.create_table(
        "organization_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), server_default="developer", nullable=False),
        sa.Column("invited_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_user"),
    )
    op.create_index("ix_org_members_org_id", "organization_members", ["organization_id"])
    op.create_index("ix_org_members_user_id", "organization_members", ["user_id"])

    # ── repositories ─────────────────────────────────────────────
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_repo_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(500), nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column("url", sa.String(500)),
        sa.Column("clone_url", sa.String(500)),
        sa.Column("default_branch", sa.String(100), server_default="main"),
        sa.Column("language", sa.String(50)),
        sa.Column("is_private", sa.Boolean(), server_default="true"),
        sa.Column("stars_count", sa.Integer(), server_default="0"),
        sa.Column("installation_id", sa.String(100)),
        sa.Column("access_token_encrypted", sa.String(2000)),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("webhook_id", sa.String(100)),
        sa.Column("webhook_secret_encrypted", sa.String(500)),
        sa.Column("webhook_active", sa.Boolean(), server_default="false"),
        sa.Column("has_read_access", sa.Boolean(), server_default="true"),
        sa.Column("has_write_access", sa.Boolean(), server_default="false"),
        sa.Column("has_check_access", sa.Boolean(), server_default="false"),
        sa.Column("can_create_pr", sa.Boolean(), server_default="false"),
        sa.Column("can_post_comments", sa.Boolean(), server_default="false"),
        sa.Column("scan_enabled", sa.Boolean(), server_default="true"),
        sa.Column("scan_on_pr", sa.Boolean(), server_default="true"),
        sa.Column("scan_on_push", sa.Boolean(), server_default="false"),
        sa.Column("scan_branches", postgresql.JSON()),
        sa.Column("auto_fix_enabled", sa.Boolean(), server_default="false"),
        sa.Column("auto_fix_mode", sa.String(50), server_default="suggest"),
        sa.Column("auto_fix_branch_prefix", sa.String(50), server_default="codesentinel/fix"),
        sa.Column("block_on_critical", sa.Boolean(), server_default="true"),
        sa.Column("block_on_high", sa.Boolean(), server_default="false"),
        sa.Column("block_on_secret", sa.Boolean(), server_default="true"),
        sa.Column("require_review_threshold", sa.String(20), server_default="high"),
        sa.Column("compliance_profiles", postgresql.JSON()),
        sa.Column("codeowners", postgresql.JSON()),
        sa.Column("total_scans", sa.Integer(), server_default="0"),
        sa.Column("total_findings", sa.Integer(), server_default="0"),
        sa.Column("open_findings", sa.Integer(), server_default="0"),
        sa.Column("last_scan_at", sa.DateTime(timezone=True)),
        sa.Column("last_scan_risk_score", sa.Integer()),
        sa.Column("connection_status", sa.String(20), server_default="connected"),
        sa.Column("connection_error", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_repos_org_id", "repositories", ["organization_id"])
    op.create_index("ix_repos_provider_id", "repositories", ["provider_repo_id"])
    op.create_index("ix_repos_installation", "repositories", ["installation_id"])

    # ── scans ─────────────────────────────────────────────────────
    op.create_table(
        "scans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("pr_number", sa.Integer()),
        sa.Column("pr_title", sa.String(500)),
        sa.Column("pr_url", sa.String(500)),
        sa.Column("pr_author", sa.String(200)),
        sa.Column("branch", sa.String(200)),
        sa.Column("base_branch", sa.String(200)),
        sa.Column("commit_sha", sa.String(40)),
        sa.Column("commit_message", sa.String(1000)),
        sa.Column("compare_url", sa.String(500)),
        sa.Column("files_changed", postgresql.JSON()),
        sa.Column("files_scanned_count", sa.Integer(), server_default="0"),
        sa.Column("lines_scanned", sa.Integer(), server_default="0"),
        sa.Column("scan_scope", sa.String(50), server_default="diff"),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("agent_states", postgresql.JSON()),
        sa.Column("agent_results", postgresql.JSON()),
        sa.Column("agent_errors", postgresql.JSON()),
        sa.Column("agent_durations", postgresql.JSON()),
        sa.Column("risk_score", sa.Integer()),
        sa.Column("risk_level", sa.String(20)),
        sa.Column("findings_total", sa.Integer(), server_default="0"),
        sa.Column("findings_critical", sa.Integer(), server_default="0"),
        sa.Column("findings_high", sa.Integer(), server_default="0"),
        sa.Column("findings_medium", sa.Integer(), server_default="0"),
        sa.Column("findings_low", sa.Integer(), server_default="0"),
        sa.Column("findings_info", sa.Integer(), server_default="0"),
        sa.Column("secrets_found", sa.Integer(), server_default="0"),
        sa.Column("dependencies_vulnerable", sa.Integer(), server_default="0"),
        sa.Column("fixes_available", sa.Integer(), server_default="0"),
        sa.Column("fixes_applied", sa.Integer(), server_default="0"),
        sa.Column("ai_provider", sa.String(50)),
        sa.Column("ai_model", sa.String(100)),
        sa.Column("ai_tokens_used", sa.Integer(), server_default="0"),
        sa.Column("compliance_results", postgresql.JSON()),
        sa.Column("merge_blocked", sa.Boolean(), server_default="false"),
        sa.Column("merge_block_reason", sa.String(500)),
        sa.Column("check_run_id", sa.String(100)),
        sa.Column("check_run_url", sa.String(500)),
        sa.Column("pr_review_id", sa.String(100)),
        sa.Column("celery_task_id", sa.String(100)),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scans_repo_id", "scans", ["repository_id"])
    op.create_index("ix_scans_status", "scans", ["status"])
    op.create_index("ix_scans_created_at", "scans", ["created_at"])

    # ── findings ──────────────────────────────────────────────────
    op.create_table(
        "findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scan_id", sa.String(36), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("rule_id", sa.String(200)),
        sa.Column("cve_id", sa.String(50)),
        sa.Column("cwe_id", sa.String(50)),
        sa.Column("owasp_category", sa.String(100)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("business_risk", sa.Text()),
        sa.Column("why_flagged", sa.Text()),
        sa.Column("recommendation", sa.Text()),
        sa.Column("references", postgresql.JSON()),
        sa.Column("file_path", sa.String(1000)),
        sa.Column("line_start", sa.Integer()),
        sa.Column("line_end", sa.Integer()),
        sa.Column("column_start", sa.Integer()),
        sa.Column("code_snippet", sa.Text()),
        sa.Column("code_context", sa.Text()),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("cvss_score", sa.Float()),
        sa.Column("cvss_vector", sa.String(100)),
        sa.Column("confidence", sa.String(20), server_default="high"),
        sa.Column("category", sa.String(100)),
        sa.Column("compliance_frameworks", postgresql.JSON()),
        sa.Column("compliance_details", postgresql.JSON()),
        sa.Column("dependency_name", sa.String(255)),
        sa.Column("dependency_version", sa.String(100)),
        sa.Column("dependency_fixed_version", sa.String(100)),
        sa.Column("dependency_ecosystem", sa.String(50)),
        sa.Column("secret_type", sa.String(100)),
        sa.Column("secret_verified", sa.Boolean()),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("is_false_positive", sa.Boolean(), server_default="false"),
        sa.Column("false_positive_reason", sa.String(500)),
        sa.Column("false_positive_reported_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("false_positive_at", sa.DateTime(timezone=True)),
        sa.Column("fix_available", sa.Boolean(), server_default="false"),
        sa.Column("fix_complexity", sa.String(20)),
        sa.Column("fingerprint", sa.String(64)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"])
    op.create_index("ix_findings_repo_id", "findings", ["repository_id"])
    op.create_index("ix_findings_severity", "findings", ["severity"])
    op.create_index("ix_findings_status", "findings", ["status"])
    op.create_index("ix_findings_fingerprint", "findings", ["fingerprint"])
    op.create_index("ix_findings_rule_id", "findings", ["rule_id"])

    # ── fixes ─────────────────────────────────────────────────────
    op.create_table(
        "fixes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scan_id", sa.String(36), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fix_type", sa.String(50), nullable=False),
        sa.Column("fix_strategy", sa.String(100)),
        sa.Column("file_path", sa.String(1000)),
        sa.Column("original_code", sa.Text()),
        sa.Column("fixed_code", sa.Text()),
        sa.Column("diff_patch", sa.Text()),
        sa.Column("diff_stats", postgresql.JSON()),
        sa.Column("description", sa.Text()),
        sa.Column("why_safe", sa.Text()),
        sa.Column("step_by_step", sa.Text()),
        sa.Column("sandbox_status", sa.String(30), server_default="pending"),
        sa.Column("sandbox_test_output", sa.Text()),
        sa.Column("sandbox_lint_output", sa.Text()),
        sa.Column("sandbox_duration_seconds", sa.Float()),
        sa.Column("sandbox_checks_passed", postgresql.JSON()),
        sa.Column("sandbox_checks_failed", postgresql.JSON()),
        sa.Column("tests_passed", sa.Integer()),
        sa.Column("tests_failed", sa.Integer()),
        sa.Column("tests_run", sa.Integer()),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("fix_branch", sa.String(200)),
        sa.Column("fix_commit_sha", sa.String(40)),
        sa.Column("fix_pr_number", sa.Integer()),
        sa.Column("fix_pr_url", sa.String(500)),
        sa.Column("applied_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("application_error", sa.String(1000)),
        sa.Column("ai_provider", sa.String(50)),
        sa.Column("ai_model", sa.String(100)),
        sa.Column("ai_prompt_tokens", sa.Integer()),
        sa.Column("ai_completion_tokens", sa.Integer()),
        sa.Column("is_verified", sa.Boolean(), server_default="false"),
        sa.Column("verification_method", sa.String(100)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_fixes_finding_id", "fixes", ["finding_id"])
    op.create_index("ix_fixes_status", "fixes", ["status"])

    # ── audit_logs ────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="SET NULL")),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_email", sa.String(255)),
        sa.Column("actor_role", sa.String(50)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", sa.String(100)),
        sa.Column("resource_name", sa.String(500)),
        sa.Column("details", postgresql.JSON()),
        sa.Column("old_value", postgresql.JSON()),
        sa.Column("new_value", postgresql.JSON()),
        sa.Column("result", sa.String(20), server_default="success"),
        sa.Column("error_message", sa.String(500)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("request_id", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # ── policies ──────────────────────────────────────────────────
    op.create_table(
        "policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column("policy_type", sa.String(50), nullable=False),
        sa.Column("severity_threshold", sa.String(20)),
        sa.Column("policy_config", postgresql.JSON()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("applies_to_repos", postgresql.JSON()),
        sa.Column("applies_to_branches", postgresql.JSON()),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policies_org_id", "policies", ["organization_id"])

    # ── notification_configs ──────────────────────────────────────
    op.create_table(
        "notification_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("config_encrypted", sa.Text()),
        sa.Column("triggers", postgresql.JSON()),
        sa.Column("severity_filter", postgresql.JSON()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notif_configs_org_id", "notification_configs", ["organization_id"])

    # ── integrations ──────────────────────────────────────────────
    op.create_table(
        "integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("config_encrypted", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_integrations_org_id", "integrations", ["organization_id"])


def downgrade() -> None:
    op.drop_table("integrations")
    op.drop_table("notification_configs")
    op.drop_table("policies")
    op.drop_table("audit_logs")
    op.drop_table("fixes")
    op.drop_table("findings")
    op.drop_table("scans")
    op.drop_table("repositories")
    op.drop_table("organization_members")
    op.drop_constraint("fk_users_primary_org", "users", type_="foreignkey")
    op.drop_table("organizations")
    op.drop_table("users")
