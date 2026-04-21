"""
CodeSentinel — GitHub Service
Real GitHub App integration:
  - JWT-based App authentication
  - Installation access token exchange
  - Repository file fetching (diff, file contents)
  - PR review and check run posting
  - Webhook validation
"""
from __future__ import annotations

import base64
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt as pyjwt
import structlog

from app.core.config import settings
from app.core.security import encryption

log = structlog.get_logger("services.github")

GITHUB_API = "https://api.github.com"


class GitHubAppError(Exception):
    pass


class GitHubAuthError(GitHubAppError):
    pass


class GitHubPermissionError(GitHubAppError):
    pass


def _generate_app_jwt() -> str:
    """
    Generate a GitHub App JWT for App-level API calls.
    Valid for 10 minutes. Uses RS256 with the App's private key.
    """
    if not settings.GITHUB_APP_ID or not settings.github_app_pem:
        raise GitHubAuthError(
            "GitHub App not configured. Set GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, "
            "and GITHUB_APP_WEBHOOK_SECRET in your .env file."
        )

    now = int(time.time())
    payload = {
        "iat": now - 60,  # 60s back to account for clock skew
        "exp": now + (10 * 60),  # 10 minutes
        "iss": settings.GITHUB_APP_ID,
    }
    try:
        return pyjwt.encode(payload, settings.github_app_pem, algorithm="RS256")
    except Exception as exc:
        raise GitHubAuthError(
            "GitHub App private key is invalid or malformed in environment configuration. "
            "Ensure GITHUB_APP_PRIVATE_KEY is the full PEM key with BEGIN/END lines."
        ) from exc


async def get_installation_access_token(installation_id: str) -> tuple[str, datetime]:
    """
    Exchange installation_id for a temporary access token (1-hour TTL).
    Returns (token, expires_at).
    """
    app_jwt = _generate_app_jwt()

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        if resp.status_code == 401:
            raise GitHubAuthError("GitHub App JWT is invalid. Check GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY.")
        if resp.status_code == 403:
            raise GitHubPermissionError(f"Installation {installation_id} lacks required permissions.")
        if resp.status_code == 404:
            raise GitHubAuthError(f"Installation {installation_id} not found. App may not be installed on this repo.")
        resp.raise_for_status()

        data = resp.json()
        token = data["token"]
        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        return token, expires_at


async def get_authenticated_headers(installation_id: str) -> dict:
    """Get auth headers using installation token."""
    token, _ = await get_installation_access_token(installation_id)
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def fetch_pull_request_diff(
    installation_id: str,
    repo_full_name: str,
    pr_number: int,
) -> str:
    """Fetch the raw diff for a pull request."""
    headers = await get_authenticated_headers(installation_id)
    headers["Accept"] = "application/vnd.github.v3.diff"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.text


async def fetch_pr_changed_files(
    installation_id: str,
    repo_full_name: str,
    pr_number: int,
) -> list[dict]:
    """Fetch list of files changed in a PR with their patches."""
    headers = await get_authenticated_headers(installation_id)

    all_files = []
    page = 1
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/files",
                headers=headers,
                params={"per_page": 100, "page": page},
            )
            resp.raise_for_status()
            files = resp.json()
            if not files:
                break
            all_files.extend(files)
            if len(files) < 100:
                break
            page += 1

    return all_files


async def fetch_file_content(
    installation_id: str,
    repo_full_name: str,
    file_path: str,
    ref: str = "HEAD",
) -> Optional[str]:
    """Fetch a specific file's content from the repository."""
    headers = await get_authenticated_headers(installation_id)

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{repo_full_name}/contents/{file_path}",
            headers=headers,
            params={"ref": ref},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        data = resp.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return data.get("content", "")


async def fetch_repository_manifests(
    installation_id: str,
    repo_full_name: str,
    ref: str = "HEAD",
) -> dict[str, str]:
    """
    Fetch dependency manifests from the repository root and common paths.
    Returns {file_path: content} dict.
    """
    manifest_paths = [
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-prod.txt",
        "package.json",
        "go.mod",
        "Cargo.toml",
        "Gemfile.lock",
        "pom.xml",
        "build.gradle",
        "pyproject.toml",
    ]

    manifests: dict[str, str] = {}
    for path in manifest_paths:
        content = await fetch_file_content(installation_id, repo_full_name, path, ref)
        if content:
            manifests[path] = content

    return manifests


async def create_check_run(
    installation_id: str,
    repo_full_name: str,
    head_sha: str,
    name: str = "CodeSentinel Security Scan",
    status: str = "in_progress",
    conclusion: Optional[str] = None,
    output: Optional[dict] = None,
) -> dict:
    """Create or update a GitHub Check Run on a PR."""
    headers = await get_authenticated_headers(installation_id)

    body: dict = {
        "name": name,
        "head_sha": head_sha,
        "status": status,
    }
    if conclusion:
        body["conclusion"] = conclusion
    if output:
        body["output"] = output
    if status == "completed" and not conclusion:
        body["conclusion"] = "neutral"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{repo_full_name}/check-runs",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        return resp.json()


async def update_check_run(
    installation_id: str,
    repo_full_name: str,
    check_run_id: str,
    status: str,
    conclusion: Optional[str] = None,
    output: Optional[dict] = None,
) -> dict:
    """Update an existing check run."""
    headers = await get_authenticated_headers(installation_id)

    body: dict = {"status": status}
    if conclusion:
        body["conclusion"] = conclusion
    if output:
        body["output"] = output

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.patch(
            f"{GITHUB_API}/repos/{repo_full_name}/check-runs/{check_run_id}",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        return resp.json()


async def post_pr_review(
    installation_id: str,
    repo_full_name: str,
    pr_number: int,
    body: str,
    event: str = "COMMENT",  # COMMENT|APPROVE|REQUEST_CHANGES
    comments: Optional[list[dict]] = None,
) -> dict:
    """Post a review comment on a pull request."""
    headers = await get_authenticated_headers(installation_id)

    payload: dict = {"body": body, "event": event}
    if comments:
        payload["comments"] = comments

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/reviews",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def create_fix_branch_and_pr(
    installation_id: str,
    repo_full_name: str,
    base_branch: str,
    branch_name: str,
    file_path: str,
    fixed_content: str,
    original_sha: str,
    commit_message: str,
    pr_title: str,
    pr_body: str,
) -> dict:
    """
    Create a fix branch, commit the patched file, and open a PR.
    Requires write access. Returns PR data.
    """
    headers = await get_authenticated_headers(installation_id)

    async with httpx.AsyncClient(timeout=20.0) as client:
        # Get base branch SHA
        ref_resp = await client.get(
            f"{GITHUB_API}/repos/{repo_full_name}/git/refs/heads/{base_branch}",
            headers=headers,
        )
        ref_resp.raise_for_status()
        base_sha = ref_resp.json()["object"]["sha"]

        # Create fix branch
        branch_resp = await client.post(
            f"{GITHUB_API}/repos/{repo_full_name}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        )
        if branch_resp.status_code not in (201, 422):  # 422 = already exists
            branch_resp.raise_for_status()

        # Update file on new branch
        encoded = base64.b64encode(fixed_content.encode()).decode()
        commit_resp = await client.put(
            f"{GITHUB_API}/repos/{repo_full_name}/contents/{file_path}",
            headers=headers,
            json={
                "message": commit_message,
                "content": encoded,
                "sha": original_sha,
                "branch": branch_name,
            },
        )
        commit_resp.raise_for_status()

        # Open PR
        pr_resp = await client.post(
            f"{GITHUB_API}/repos/{repo_full_name}/pulls",
            headers=headers,
            json={
                "title": pr_title,
                "body": pr_body,
                "head": branch_name,
                "base": base_branch,
            },
        )
        pr_resp.raise_for_status()
        return pr_resp.json()


async def get_installation_repos(installation_id: str) -> list[dict]:
    """List repositories accessible to this App installation."""
    headers = await get_authenticated_headers(installation_id)
    all_repos = []
    page = 1

    async with httpx.AsyncClient(timeout=20.0) as client:
        while True:
            resp = await client.get(
                f"{GITHUB_API}/installation/repositories",
                headers=headers,
                params={"per_page": 100, "page": page},
            )
            resp.raise_for_status()
            data = resp.json()
            repos = data.get("repositories", [])
            all_repos.extend(repos)
            if len(repos) < 100:
                break
            page += 1

    return all_repos


async def list_app_installations() -> list[dict]:
    """List all installations of this GitHub App."""
    app_jwt = _generate_app_jwt()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{GITHUB_API}/app/installations",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        resp.raise_for_status()
        return resp.json()
