"""
CodeSentinel — Test Account Seed Script
Creates the test user with a pre-seeded organization.
Run ONCE after DB migrations: python scripts/seed_test_account.py

Test credentials (share only in chat, NEVER in the UI):
  Email:    sentinel.test@codesentinel.dev
  Password: CodeSentinel#Test2024

This account has is_test_user=True which enables:
  - The guided product tour on first login
  - Tour highlights overlaid on every page
  - A clearly visible "Test Account" badge in the sidebar
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_context
from app.core.security import hash_password, UserRole
from app.models.user import User
from sqlalchemy import select, text
import uuid
from datetime import datetime, timezone


TEST_EMAIL = "sentinel.test@codesentinel.dev"
TEST_PASSWORD = "CodeSentinel#Test2024"
TEST_ORG_NAME = "CodeSentinel Demo Org"
TEST_ORG_SLUG = "codesentinel-demo"


async def seed():
    async with get_db_context() as db:
        # Check if already exists
        existing = await db.execute(select(User).where(User.email == TEST_EMAIL))
        if existing.scalar_one_or_none():
            print(f"✓ Test account already exists: {TEST_EMAIL}")
            return

        user_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        hashed_password = hash_password(TEST_PASSWORD)

        await db.execute(
            text(
                """
                INSERT INTO users (
                    id, email, hashed_password, full_name, job_title, company,
                    primary_org_id, is_active, is_verified, is_test_user,
                    tour_completed, tour_step, created_at, updated_at
                ) VALUES (
                    :id, :email, :hashed_password, :full_name, :job_title, :company,
                    NULL, :is_active, :is_verified, :is_test_user,
                    :tour_completed, :tour_step, :created_at, :updated_at
                )
                """
            ),
            {
                "id": user_id,
                "email": TEST_EMAIL,
                "hashed_password": hashed_password,
                "full_name": "Demo Security Engineer",
                "job_title": "Security Engineer",
                "company": "CodeSentinel Demo",
                "is_active": True,
                "is_verified": True,
                "is_test_user": True,
                "tour_completed": False,
                "tour_step": 0,
                "created_at": now,
                "updated_at": now,
            },
        )

        await db.execute(
            text(
                """
                INSERT INTO organizations (
                    id, name, slug, owner_id, plan, max_repos, max_members,
                    max_scans_per_month, scans_this_month, org_settings,
                    compliance_profiles, ai_provider_preference,
                    auto_fix_enabled, secret_scanning_enabled, sbom_export_enabled,
                    pr_blocking_enabled, created_at, updated_at
                ) VALUES (
                    :id, :name, :slug, :owner_id, :plan, :max_repos, :max_members,
                    :max_scans_per_month, :scans_this_month, :org_settings,
                    :compliance_profiles, :ai_provider_preference,
                    :auto_fix_enabled, :secret_scanning_enabled, :sbom_export_enabled,
                    :pr_blocking_enabled, :created_at, :updated_at
                )
                """
            ),
            {
                "id": org_id,
                "name": TEST_ORG_NAME,
                "slug": TEST_ORG_SLUG,
                "owner_id": user_id,
                "plan": "pro",
                "max_repos": 5,
                "max_members": 3,
                "max_scans_per_month": 100,
                "scans_this_month": 0,
                "org_settings": json.dumps({}),
                "compliance_profiles": json.dumps(["soc2", "hipaa", "pci_dss", "gdpr"]),
                "ai_provider_preference": "ollama",
                "auto_fix_enabled": True,
                "secret_scanning_enabled": True,
                "sbom_export_enabled": True,
                "pr_blocking_enabled": True,
                "created_at": now,
                "updated_at": now,
            },
        )

        await db.execute(
            text("UPDATE users SET primary_org_id = :org_id, updated_at = :updated_at WHERE id = :user_id"),
            {"org_id": org_id, "updated_at": now, "user_id": user_id},
        )

        await db.execute(
            text(
                """
                INSERT INTO organization_members (
                    id, organization_id, user_id, role, accepted_at, created_at
                ) VALUES (
                    :id, :organization_id, :user_id, :role, :accepted_at, :created_at
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "user_id": user_id,
                "role": UserRole.OWNER.value,
                "accepted_at": now,
                "created_at": now,
            },
        )
        await db.commit()

        print(f"✅ Test account created successfully:")
        print(f"   Email:    {TEST_EMAIL}")
        print(f"   Password: {TEST_PASSWORD}")
        print(f"   Org:      {TEST_ORG_NAME}")
        print(f"")
        print(f"   NOTE: Keep these credentials private — share only in chat, never in UI.")
        print(f"   This account has is_test_user=True which enables the product tour.")


if __name__ == "__main__":
    asyncio.run(seed())
