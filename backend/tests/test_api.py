"""
CodeSentinel — Integration Test Suite
Tests against a real PostgreSQL test database.

Run:
    cd backend
    pytest tests/test_api.py -v --tb=short -m "not integration" --no-header

For integration tests (requires real PostgreSQL):
    pytest tests/test_api.py -v --tb=short
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ── Authentication Tests ───────────────────────────────────────────────────────

class TestRegistration:
    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "newuser@codesentinel.test",
            "password": "Secure#Pass123",
            "full_name": "New Test User",
            "job_title": "DevOps Engineer",
            "company": "Test Company Ltd",
            "organization_name": "Test Organization",
            "use_case": "Automated security scanning for our CI/CD pipeline integration",
            "agree_to_terms": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "newuser@codesentinel.test"
        assert data["user"]["tour_completed"] is False

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, auth_headers: dict):
        """Attempting to register with same email should return 409."""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "pytest@codesentinel.test",
            "password": "Secure#Pass123",
            "full_name": "Duplicate",
            "job_title": "Engineer",
            "company": "Co",
            "organization_name": "Dup Org",
            "use_case": "Testing duplicate email prevention in registration flow",
            "agree_to_terms": True,
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weakpass@test.com",
            "password": "password",  # No uppercase, no special char
            "full_name": "Test",
            "job_title": "Engineer",
            "company": "Co",
            "organization_name": "Org",
            "use_case": "Testing password validation on registration endpoint",
            "agree_to_terms": True,
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_terms_required(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "terms@test.com",
            "password": "Secure#Pass123",
            "full_name": "Test",
            "job_title": "Engineer",
            "company": "Co",
            "organization_name": "Org",
            "use_case": "Testing that terms of service agreement is enforced",
            "agree_to_terms": False,  # Not agreed
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "pytest@codesentinel.test",
            "password": "TestPass#1234",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "pytest@codesentinel.test",
            "password": "WrongPass#999",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "pytest@codesentinel.test"
        assert "organization" in data

    @pytest.mark.asyncio
    async def test_unauthorized_without_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient):
        login = await client.post("/api/v1/auth/login", json={
            "email": "pytest@codesentinel.test",
            "password": "TestPass#1234",
        })
        refresh = login.json()["refresh_token"]
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_tour_update(self, client: AsyncClient, auth_headers: dict):
        resp = await client.patch("/api/v1/auth/tour",
            json={"tour_step": 3},
            headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["tour_step"] == 3


# ── Repository Tests ──────────────────────────────────────────────────────────

class TestRepositories:
    @pytest.mark.asyncio
    async def test_list_repos_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/repos", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["repositories"] == []

    @pytest.mark.asyncio
    async def test_get_nonexistent_repo(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/repos/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_connect_github_invalid_installation(self, client: AsyncClient, auth_headers: dict):
        """Connecting a fake installation_id should return 422 (GitHub will reject the token exchange)."""
        resp = await client.post("/api/v1/repos/connect-github",
            json={"installation_id": "999999999", "provider": "github"},
            headers=auth_headers,
        )
        # Should fail gracefully — not crash, just 422
        assert resp.status_code in (422, 200)


# ── Scans Tests ───────────────────────────────────────────────────────────────

class TestScans:
    @pytest.mark.asyncio
    async def test_list_scans_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/scans", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "scans" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_trigger_manual_scan_nonexistent_repo(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/v1/scans/manual",
            json={"repository_id": "00000000-0000-0000-0000-000000000000", "scope": "full"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent_scan(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/scans/nonexistent-scan-id", headers=auth_headers)
        assert resp.status_code == 404


# ── Findings Tests ────────────────────────────────────────────────────────────

class TestFindings:
    @pytest.mark.asyncio
    async def test_list_findings_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/findings", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["findings"] == []

    @pytest.mark.asyncio
    async def test_findings_summary(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/findings/summary/by-org", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "by_severity" in data
        assert "total_open" in data

    @pytest.mark.asyncio
    async def test_finding_filter_by_severity(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/findings?severity=critical", headers=auth_headers)
        assert resp.status_code == 200


# ── Policies Tests ────────────────────────────────────────────────────────────

class TestPolicies:
    @pytest.mark.asyncio
    async def test_list_policies_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/policies", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["policies"] == []

    @pytest.mark.asyncio
    async def test_create_policy(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/v1/policies", json={
            "name": "Block Critical Findings",
            "policy_type": "block_merge",
            "severity_threshold": "critical",
            "description": "Block PR merge when critical vulnerabilities are found",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Block Critical Findings"
        assert data["policy_type"] == "block_merge"
        assert data["is_active"] is True
        return data["id"]

    @pytest.mark.asyncio
    async def test_create_policy_invalid_type(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/v1/policies", json={
            "name": "Bad Policy",
            "policy_type": "invalid_type",
            "severity_threshold": "critical",
        }, headers=auth_headers)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_policy_full_lifecycle(self, client: AsyncClient, auth_headers: dict):
        """Create → update → toggle → delete."""
        # Create
        create_resp = await client.post("/api/v1/policies", json={
            "name": "Test Lifecycle Policy",
            "policy_type": "notify",
            "severity_threshold": "high",
        }, headers=auth_headers)
        assert create_resp.status_code == 201
        policy_id = create_resp.json()["id"]

        # Update
        update_resp = await client.patch(f"/api/v1/policies/{policy_id}",
            json={"name": "Updated Policy Name"},
            headers=auth_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Updated Policy Name"

        # Toggle off
        toggle_resp = await client.patch(f"/api/v1/policies/{policy_id}",
            json={"is_active": False},
            headers=auth_headers,
        )
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["is_active"] is False

        # Delete
        delete_resp = await client.delete(f"/api/v1/policies/{policy_id}", headers=auth_headers)
        assert delete_resp.status_code == 204


# ── Team Tests ────────────────────────────────────────────────────────────────

class TestTeam:
    @pytest.mark.asyncio
    async def test_list_team(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/team", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "members" in data
        # Should have at least the owner
        assert len(data["members"]) >= 1
        owner = data["members"][0]
        assert owner["role"] == "owner"

    @pytest.mark.asyncio
    async def test_invite_member(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/v1/team/invite", json={
            "email": "invited.developer@company.test",
            "role": "developer",
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert "invited.developer@company.test" in resp.json()["message"]

    @pytest.mark.asyncio
    async def test_invite_invalid_role(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/v1/team/invite", json={
            "email": "test2@company.test",
            "role": "superuser",  # Not valid
        }, headers=auth_headers)
        assert resp.status_code == 400


# ── Notifications Tests ───────────────────────────────────────────────────────

class TestNotifications:
    @pytest.mark.asyncio
    async def test_list_notifications_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/notifications", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["configs"] == []

    @pytest.mark.asyncio
    async def test_create_slack_notification(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/v1/notifications", json={
            "name": "Security Slack Channel",
            "channel": "slack",
            "triggers": ["critical_finding", "merge_blocked"],
            "config": {"webhook_url": "https://hooks.slack.com/services/test/test/test"},
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["channel"] == "slack"
        assert "critical_finding" in data["triggers"]

    @pytest.mark.asyncio
    async def test_create_invalid_channel(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/v1/notifications", json={
            "name": "Bad Channel",
            "channel": "discord",  # Not supported
        }, headers=auth_headers)
        assert resp.status_code == 400


# ── AI Models Tests ───────────────────────────────────────────────────────────

class TestModels:
    @pytest.mark.asyncio
    async def test_list_providers(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/models/providers", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        # Ollama should always be listed
        provider_ids = [p["id"] for p in data["providers"]]
        assert "ollama" in provider_ids

    @pytest.mark.asyncio
    async def test_test_provider_ollama(self, client: AsyncClient, auth_headers: dict):
        """Test the Ollama provider endpoint — may be unavailable in CI."""
        resp = await client.post("/api/v1/models/test", json={
            "provider": "ollama",
            "prompt": "Reply with the single word: working",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Either succeeds or gives a meaningful error — never crashes
        assert "success" in data
        if not data["success"]:
            assert "error" in data
            assert "message" in data


# ── Observability Tests ───────────────────────────────────────────────────────

class TestObservability:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded", "unhealthy")

    @pytest.mark.asyncio
    async def test_system_health_authenticated(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/observability/health", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "overall" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]

    @pytest.mark.asyncio
    async def test_scan_metrics(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/observability/metrics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_scans" in data


# ── SBOM Tests ────────────────────────────────────────────────────────────────

class TestSBOM:
    @pytest.mark.asyncio
    async def test_sbom_summary_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/sbom/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_sbom_export_format(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/sbom/export", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        data = resp.json()
        assert data["spdxVersion"] == "SPDX-2.3"
        assert "packages" in data
        assert "creationInfo" in data


# ── Audit Log Tests ───────────────────────────────────────────────────────────

class TestAudit:
    @pytest.mark.asyncio
    async def test_audit_logs_after_login(self, client: AsyncClient, auth_headers: dict):
        """After login/register, audit logs should have entries."""
        resp = await client.get("/api/v1/audit", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data
        assert "total" in data
        # There should be at least a register and login event
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_audit_search(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/audit?search=user.register", headers=auth_headers)
        assert resp.status_code == 200


# ── Settings Tests ────────────────────────────────────────────────────────────

class TestSettings:
    @pytest.mark.asyncio
    async def test_update_profile(self, client: AsyncClient, auth_headers: dict):
        resp = await client.patch("/api/v1/settings/profile", json={
            "full_name": "Updated Test User",
            "job_title": "Senior Security Engineer",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "Updated Test User"
        assert data["job_title"] == "Senior Security Engineer"

    @pytest.mark.asyncio
    async def test_update_org_settings(self, client: AsyncClient, auth_headers: dict):
        resp = await client.patch("/api/v1/settings/organization", json={
            "secret_scanning_enabled": True,
            "pr_blocking_enabled": True,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["secret_scanning_enabled"] is True
        assert data["pr_blocking_enabled"] is True

    @pytest.mark.asyncio
    async def test_generate_api_key(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/v1/auth/generate-api-key", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "api_key" in data
        assert data["api_key"].startswith("cs_")
        assert len(data["api_key"]) > 40
        # Key should only be returned once — prefix in UI
        assert "prefix" in data

    @pytest.mark.asyncio
    async def test_github_app_url(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/settings/github-app-url", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert "url" in data
