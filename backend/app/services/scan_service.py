"""
CodeSentinel — Scan Orchestration Service
Coordinates the five-agent pipeline for a scan job.
Called by Celery tasks; persists everything to PostgreSQL in real time.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.base_agent import AgentContext
from app.agents.static_agent import StaticAnalysisAgent
from app.agents.dependency_agent import DependencyAgent
from app.agents.business_logic_agent import BusinessLogicAgent
from app.agents.autofix_agent import AutoFixAgent
from app.agents.compliance_agent import ComplianceAgent
from app.core.database import get_db_context
from app.models.finding import Finding
from app.models.fix import Fix
from app.models.scan import Scan
from app.models.repository import Repository
from app.services.github_service import (
    fetch_pull_request_diff,
    fetch_pr_changed_files,
    fetch_file_content,
    fetch_repository_manifests,
    create_check_run,
    update_check_run,
    post_pr_review,
    GitHubAppError,
)

log = structlog.get_logger("services.scan")

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _calculate_risk_score(findings: list[dict]) -> int:
    """Compute 0-100 risk score weighted by severity."""
    if not findings:
        return 0
    weights = {"critical": 40, "high": 20, "medium": 8, "low": 2, "info": 0}
    raw = sum(weights.get(f.get("severity", "info"), 0) for f in findings)
    return min(100, raw)


def _risk_level(score: int) -> str:
    if score >= 80:
        return "critical"
    elif score >= 50:
        return "high"
    elif score >= 20:
        return "medium"
    elif score > 0:
        return "low"
    return "none"


async def run_scan_pipeline(scan_id: str) -> None:
    """
    Main entry point for running the complete 5-agent security scan pipeline.
    Called by Celery. All state changes persisted to DB.
    """
    log.info("Scan pipeline starting", scan_id=scan_id)
    pipeline_start = time.perf_counter()

    async with get_db_context() as db:
        # Load scan + repo
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()
        if not scan:
            log.error("Scan not found", scan_id=scan_id)
            return

        result = await db.execute(select(Repository).where(Repository.id == scan.repository_id))
        repo = result.scalar_one_or_none()
        if not repo:
            log.error("Repository not found for scan", scan_id=scan_id, repo_id=scan.repository_id)
            return

        # Transition to running
        scan.status = "running"
        scan.started_at = datetime.now(timezone.utc)
        await db.commit()

    # ── Fetch code from GitHub ─────────────────────────────────────
    diff_content: Optional[str] = None
    file_contents: dict[str, str] = {}
    manifests: dict[str, str] = {}
    check_run_id: Optional[str] = None

    try:
        if repo.installation_id:
            # Create a pending check run on GitHub
            if repo.has_check_access and scan.commit_sha:
                try:
                    check_data = await create_check_run(
                        installation_id=repo.installation_id,
                        repo_full_name=repo.full_name,
                        head_sha=scan.commit_sha,
                        name="CodeSentinel Security Scan",
                        status="in_progress",
                        output={
                            "title": "Security scan in progress…",
                            "summary": "Running 5-agent security analysis pipeline.",
                        },
                    )
                    check_run_id = str(check_data.get("id", ""))
                    async with get_db_context() as db:
                        result = await db.execute(select(Scan).where(Scan.id == scan_id))
                        scan_row = result.scalar_one_or_none()
                        if scan_row:
                            scan_row.check_run_id = check_run_id
                            scan_row.check_run_url = check_data.get("html_url")
                            await db.commit()
                except GitHubAppError as exc:
                    log.warning("Could not create check run", scan_id=scan_id, error=str(exc))

            # Fetch diff for PR scans
            if scan.pr_number:
                try:
                    diff_content = await fetch_pull_request_diff(
                        repo.installation_id, repo.full_name, scan.pr_number
                    )
                    changed_files = await fetch_pr_changed_files(
                        repo.installation_id, repo.full_name, scan.pr_number
                    )
                    # Fetch content for each changed file
                    for file_info in changed_files[:20]:  # Limit to 20 files
                        path = file_info.get("filename", "")
                        if path and not _should_skip_file(path):
                            content = await fetch_file_content(
                                repo.installation_id, repo.full_name, path,
                                ref=scan.commit_sha or "HEAD",
                            )
                            if content:
                                file_contents[path] = content
                except GitHubAppError as exc:
                    log.warning("Could not fetch PR diff", scan_id=scan_id, error=str(exc))

            # Fetch manifests
            try:
                manifests = await fetch_repository_manifests(
                    repo.installation_id, repo.full_name,
                    ref=scan.commit_sha or "HEAD",
                )
            except GitHubAppError as exc:
                log.warning("Could not fetch manifests", scan_id=scan_id, error=str(exc))

    except Exception as exc:
        log.error("Fatal error fetching code from GitHub", scan_id=scan_id, error=str(exc), exc_info=True)
        async with get_db_context() as db:
            result = await db.execute(select(Scan).where(Scan.id == scan_id))
            scan_row = result.scalar_one_or_none()
            if scan_row:
                scan_row.status = "failed"
                scan_row.agent_errors = {"pipeline": str(exc)}
                await db.commit()
        return

    # ── Build agent context ────────────────────────────────────────
    ctx = AgentContext(
        scan_id=scan_id,
        repository_id=str(repo.id),
        organization_id=str(repo.organization_id),
        diff_content=diff_content,
        file_contents=file_contents,
        manifests=manifests,
        repo_full_name=repo.full_name,
        repo_default_branch=repo.default_branch,
        repo_language=repo.language,
        compliance_profiles=repo.compliance_profiles or [],
        ai_provider=None,  # Use org default (resolved by model_router fallback chain)
        ai_model=None,
    )

    # ── Run Agents 1, 2, 3, 5 in parallel; Agent 4 (auto-fix) after ─
    agent1 = StaticAnalysisAgent()
    agent2 = DependencyAgent()
    agent3 = BusinessLogicAgent()
    agent5 = ComplianceAgent()

    log.info("Running agents 1, 2, 3, 5 in parallel", scan_id=scan_id)

    results = await asyncio.gather(
        agent1.execute(ctx),
        agent2.execute(ctx),
        agent3.execute(ctx),
        agent5.execute(ctx),
        return_exceptions=True,
    )

    r1, r2, r3, r5 = results

    # Collect all findings from completed agents
    all_findings: list[dict] = []
    agent_results_summary: dict = {}
    agent_durations: dict = {}

    for agent_name, result in [("static", r1), ("dependency", r2), ("business_logic", r3), ("compliance", r5)]:
        if isinstance(result, Exception):
            log.error("Agent raised exception", agent=agent_name, error=str(result))
            agent_results_summary[agent_name] = {"error": str(result), "findings": 0}
        else:
            findings = result.findings or []
            all_findings.extend(findings)
            agent_results_summary[agent_name] = {
                "findings": len(findings),
                "success": result.success,
            }
            agent_durations[agent_name] = round(result.duration_seconds, 2)
            # Carry extra data (SBOM, compliance scores)
            if result.extra:
                agent_results_summary[agent_name].update(result.extra)

    # ── Run Agent 4 (Auto-Fix) with all upstream findings ──────────
    ctx.upstream_results = {
        "static": agent_results_summary.get("static", {}),
        "dependency": agent_results_summary.get("dependency", {}),
        "business_logic": agent_results_summary.get("business_logic", {}),
        "compliance": agent_results_summary.get("compliance", {}),
    }
    # Pass actual finding dicts to the fix agent
    ctx.upstream_results["_all_findings"] = [
        {**f, "agent_type": f.get("agent_type", "static")}
        for f in all_findings
    ]

    agent4 = AutoFixAgent()
    fix_result = await agent4.execute(ctx)
    agent_durations["autofix"] = round(fix_result.duration_seconds, 2)
    fix_data = fix_result.extra if fix_result.success else {}

    # ── Persist all findings to database ──────────────────────────
    async with get_db_context() as db:
        persisted_findings: list[Finding] = []
        for f_dict in all_findings:
            finding_obj = Finding(
                id=str(uuid.uuid4()),
                scan_id=scan_id,
                repository_id=str(repo.id),
                agent_type=f_dict.get("agent_type", "static"),
                rule_id=f_dict.get("rule_id"),
                cve_id=f_dict.get("cve_id"),
                cwe_id=f_dict.get("cwe_id"),
                owasp_category=f_dict.get("owasp_category"),
                title=f_dict.get("title", "Untitled Finding")[:499],
                description=f_dict.get("description", "")[:5000],
                business_risk=f_dict.get("business_risk", "")[:2000],
                why_flagged=f_dict.get("why_flagged", "")[:2000],
                recommendation=f_dict.get("recommendation", "")[:2000],
                references=f_dict.get("references", []),
                file_path=f_dict.get("file_path"),
                line_start=f_dict.get("line_start"),
                line_end=f_dict.get("line_end"),
                code_snippet=f_dict.get("code_snippet", "")[:1000] if f_dict.get("code_snippet") else None,
                code_context=f_dict.get("code_context", "")[:2000] if f_dict.get("code_context") else None,
                severity=f_dict.get("severity", "info"),
                cvss_score=f_dict.get("cvss_score"),
                cvss_vector=f_dict.get("cvss_vector"),
                confidence=f_dict.get("confidence", "medium"),
                category=f_dict.get("category"),
                compliance_frameworks=f_dict.get("compliance_frameworks", []),
                compliance_details=f_dict.get("compliance_details"),
                dependency_name=f_dict.get("dependency_name"),
                dependency_version=f_dict.get("dependency_version"),
                dependency_fixed_version=f_dict.get("dependency_fixed_version"),
                dependency_ecosystem=f_dict.get("dependency_ecosystem"),
                secret_type=f_dict.get("secret_type"),
                fix_available=f_dict.get("fix_available", False),
                fix_complexity=f_dict.get("fix_complexity"),
                fingerprint=f_dict.get("fingerprint"),
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                status="open",
            )
            db.add(finding_obj)
            persisted_findings.append(finding_obj)

        # Persist fix records
        fix_records = fix_data.get("fix_results", [])
        for fix_dict in fix_records:
            finding_id = fix_dict.get("finding_id")
            if not finding_id:
                continue
            fix_obj = Fix(
                id=str(uuid.uuid4()),
                finding_id=finding_id,
                scan_id=scan_id,
                fix_type=fix_dict.get("fix_type", "automated"),
                fix_strategy=fix_dict.get("fix_strategy"),
                file_path=fix_dict.get("file_path"),
                original_code=fix_dict.get("original_code"),
                fixed_code=fix_dict.get("fixed_code"),
                diff_patch=fix_dict.get("diff_patch"),
                diff_stats=fix_dict.get("diff_stats"),
                description=fix_dict.get("description"),
                why_safe=fix_dict.get("why_safe"),
                step_by_step=fix_dict.get("step_by_step"),
                sandbox_status=fix_dict.get("sandbox_status", "pending"),
                sandbox_test_output=fix_dict.get("sandbox_test_output"),
                sandbox_lint_output=fix_dict.get("sandbox_lint_output"),
                sandbox_checks_passed=fix_dict.get("sandbox_checks_passed"),
                sandbox_checks_failed=fix_dict.get("sandbox_checks_failed"),
                status=fix_dict.get("status", "pending"),
                is_verified=fix_dict.get("is_verified", False),
                verification_method=fix_dict.get("verification_method"),
                created_at=datetime.now(timezone.utc),
            )
            db.add(fix_obj)

        # Calculate summary metrics
        risk_score = _calculate_risk_score(all_findings)
        sev_counts = {s: 0 for s in ("critical", "high", "medium", "low", "info")}
        for f in all_findings:
            sev_counts[f.get("severity", "info")] = sev_counts.get(f.get("severity", "info"), 0) + 1

        secrets_count = sum(1 for f in all_findings if f.get("category") == "secrets" or f.get("agent_type") == "secret")
        dep_vuln_count = sum(1 for f in all_findings if f.get("agent_type") == "dependency")

        # Check merge blocking policy
        merge_blocked = False
        block_reason = None
        if repo.block_on_critical and sev_counts["critical"] > 0:
            merge_blocked = True
            block_reason = f"{sev_counts['critical']} critical vulnerability(ies) require remediation before merge."
        elif repo.block_on_secret and secrets_count > 0:
            merge_blocked = True
            block_reason = f"{secrets_count} hardcoded secret(s) detected — merge blocked."
        elif repo.block_on_high and sev_counts["high"] > 0:
            merge_blocked = True
            block_reason = f"{sev_counts['high']} high-severity vulnerability(ies) require remediation."

        # Compliance results
        compliance_results = agent_results_summary.get("compliance", {}).get("compliance_results", {})

        total_duration = time.perf_counter() - pipeline_start

        # Update scan record
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan_row = result.scalar_one_or_none()
        if scan_row:
            scan_row.status = "blocked" if merge_blocked else "completed"
            scan_row.completed_at = datetime.now(timezone.utc)
            scan_row.duration_seconds = total_duration
            scan_row.risk_score = risk_score
            scan_row.risk_level = _risk_level(risk_score)
            scan_row.findings_total = len(all_findings)
            scan_row.findings_critical = sev_counts["critical"]
            scan_row.findings_high = sev_counts["high"]
            scan_row.findings_medium = sev_counts["medium"]
            scan_row.findings_low = sev_counts["low"]
            scan_row.findings_info = sev_counts["info"]
            scan_row.secrets_found = secrets_count
            scan_row.dependencies_vulnerable = dep_vuln_count
            scan_row.fixes_available = len([f for f in fix_records if f.get("status") == "verified"])
            scan_row.agent_results = agent_results_summary
            scan_row.agent_durations = agent_durations
            scan_row.compliance_results = compliance_results
            scan_row.merge_blocked = merge_blocked
            scan_row.merge_block_reason = block_reason
            scan_row.files_scanned_count = len(file_contents)

        # Update repository cached stats
        result2 = await db.execute(select(Repository).where(Repository.id == scan_row.repository_id))
        repo_row = result2.scalar_one_or_none()
        if repo_row:
            repo_row.total_scans = (repo_row.total_scans or 0) + 1
            repo_row.total_findings = (repo_row.total_findings or 0) + len(all_findings)
            repo_row.open_findings = (repo_row.open_findings or 0) + sev_counts["critical"] + sev_counts["high"]
            repo_row.last_scan_at = datetime.now(timezone.utc)
            repo_row.last_scan_risk_score = risk_score

        await db.commit()

    # ── Post results back to GitHub ────────────────────────────────
    if repo.installation_id and scan_row:
        await _post_github_results(repo, scan_row, all_findings, risk_score, merge_blocked, block_reason, check_run_id)

    log.info(
        "Scan pipeline complete",
        scan_id=scan_id,
        findings=len(all_findings),
        risk_score=risk_score,
        merge_blocked=merge_blocked,
        duration=round(total_duration, 2),
    )


async def _post_github_results(
    repo: Repository,
    scan: Scan,
    findings: list[dict],
    risk_score: int,
    merge_blocked: bool,
    block_reason: Optional[str],
    check_run_id: Optional[str],
) -> None:
    """Post scan results back to GitHub as check run + PR review."""
    if not repo.installation_id or not repo.has_check_access:
        return

    try:
        conclusion = "failure" if merge_blocked else ("warning" if risk_score > 30 else "success")
        sev_summary = f"Critical: {scan.findings_critical} | High: {scan.findings_high} | Medium: {scan.findings_medium} | Low: {scan.findings_low}"

        check_output = {
            "title": f"CodeSentinel: Risk Score {risk_score}/100 — {sev_summary}",
            "summary": _build_check_summary(findings, risk_score, merge_blocked, block_reason),
            "text": _build_check_details(findings[:10]),  # Top 10 findings in detail
        }

        if check_run_id:
            await update_check_run(
                installation_id=repo.installation_id,
                repo_full_name=repo.full_name,
                check_run_id=check_run_id,
                status="completed",
                conclusion=conclusion,
                output=check_output,
            )

        # Post PR review if this was a PR scan
        if scan.pr_number and repo.can_post_comments:
            review_event = "REQUEST_CHANGES" if merge_blocked else "COMMENT"
            review_body = _build_pr_review_body(findings, risk_score, merge_blocked, block_reason)
            await post_pr_review(
                installation_id=repo.installation_id,
                repo_full_name=repo.full_name,
                pr_number=scan.pr_number,
                body=review_body,
                event=review_event,
            )

    except Exception as exc:
        log.error("Failed to post GitHub results", scan_id=str(scan.id), error=str(exc))


def _build_check_summary(findings: list[dict], risk_score: int, blocked: bool, block_reason: Optional[str]) -> str:
    lines = [f"## CodeSentinel Security Analysis\n"]
    lines.append(f"**Risk Score:** {risk_score}/100")
    lines.append(f"**Total Findings:** {len(findings)}")
    if blocked:
        lines.append(f"\n⛔ **MERGE BLOCKED:** {block_reason}")
    lines.append("\n### Agent Results")
    agents = {"static": "Static Analysis", "dependency": "Dependency", "business_logic": "Business Logic", "compliance": "Compliance"}
    for key, name in agents.items():
        count = sum(1 for f in findings if f.get("agent_type") == key)
        lines.append(f"- {name}: {count} findings")
    return "\n".join(lines)


def _build_check_details(findings: list[dict]) -> str:
    if not findings:
        return "No security issues found in this change."
    lines = ["## Top Findings\n"]
    for f in findings:
        sev = f.get("severity", "info").upper()
        lines.append(f"### [{sev}] {f.get('title', 'Finding')}")
        if f.get("file_path"):
            lines.append(f"**Location:** `{f['file_path']}:{f.get('line_start', '?')}`")
        lines.append(f"**Why flagged:** {f.get('why_flagged', f.get('description', ''))[:300]}")
        if f.get("recommendation"):
            lines.append(f"**Fix:** {f['recommendation'][:200]}")
        lines.append("")
    return "\n".join(lines)


def _build_pr_review_body(findings: list[dict], risk_score: int, blocked: bool, block_reason: Optional[str]) -> str:
    emoji = "⛔" if blocked else ("⚠️" if risk_score > 30 else "✅")
    lines = [f"{emoji} **CodeSentinel Security Review** — Risk Score: **{risk_score}/100**\n"]
    if blocked:
        lines.append(f"> **BLOCKED:** {block_reason}\n")
    critical = [f for f in findings if f.get("severity") == "critical"]
    high = [f for f in findings if f.get("severity") == "high"]
    if critical:
        lines.append(f"🔴 **{len(critical)} Critical** vulnerabilities require immediate attention")
    if high:
        lines.append(f"🟠 **{len(high)} High** severity issues found")
    lines.append(f"\nTotal: **{len(findings)} findings** — See CodeSentinel dashboard for full report and auto-fix suggestions.")
    return "\n".join(lines)


def _should_skip_file(path: str) -> bool:
    """Skip binary, generated, and non-code files."""
    skip_extensions = {
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
        ".ttf", ".eot", ".pdf", ".zip", ".tar", ".gz", ".lock",
        ".min.js", ".min.css", ".map",
    }
    skip_dirs = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "vendor"}
    path_lower = path.lower()
    for skip in skip_extensions:
        if path_lower.endswith(skip):
            return True
    for skip_dir in skip_dirs:
        if f"/{skip_dir}/" in path_lower or path_lower.startswith(f"{skip_dir}/"):
            return True
    return False
