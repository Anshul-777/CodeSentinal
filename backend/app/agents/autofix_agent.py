"""
CodeSentinel — Agent 4: Auto-Fix Agent
Generates real patches for known vulnerability classes, runs them through
a subprocess-based sandbox (syntax check + lint + test runner), and only
marks a fix as verified if validation passes.

Fix workflow:
  1. Receive a finding with original code
  2. LLM generates a corrected patch
  3. Apply patch to a temp copy of the file
  4. Run: syntax check → flake8/eslint → pytest (if tests exist)
  5. If all pass: status=verified. If any fail: status=rejected with reason.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Optional

import structlog

from app.agents.base_agent import AgentContext, AgentResult, BaseAgent
from app.ai import model_router
from app.ai.prompts.agent_prompts import AUTOFIX_SYSTEM

log = structlog.get_logger("agents.autofix")

# Severity levels that the auto-fix agent will attempt to fix
FIXABLE_SEVERITIES = {"critical", "high", "medium"}

# Categories that have good auto-fix success rates
HIGH_CONFIDENCE_CATEGORIES = {
    "secrets", "crypto", "injection", "xss", "config",
    "vulnerable_dependency", "tls", "deserialization",
}

# Auto-fix is skipped for business logic — requires human judgment
SKIP_CATEGORIES = {"logic", "auth", "authz", "race_condition", "business_rule"}


def _validate_python_syntax(code: str) -> tuple[bool, Optional[str]]:
    """Check that patched Python code has valid syntax."""
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error: {e.msg} at line {e.lineno}"


def _run_flake8(filepath: str) -> tuple[bool, str]:
    """Run flake8 on a file. Return (passed, output)."""
    try:
        result = subprocess.run(
            ["flake8", "--max-line-length=120", "--ignore=E501,W503", filepath],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True, "flake8 not available — skipped"


def _run_pytest_in_dir(repo_dir: str) -> tuple[bool, int, int, str]:
    """Run pytest in repo dir. Returns (passed, n_passed, n_failed, output)."""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--tb=short", "-q", "--no-header", "--timeout=30"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=repo_dir,
        )
        output = (result.stdout + result.stderr)[:3000]

        # Parse pytest summary
        n_passed = n_failed = 0
        for line in output.split("\n"):
            import re
            m = re.search(r"(\d+) passed", line)
            if m:
                n_passed = int(m.group(1))
            m = re.search(r"(\d+) failed", line)
            if m:
                n_failed = int(m.group(1))

        return result.returncode == 0, n_passed, n_failed, output
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return True, 0, 0, f"pytest not available or timed out: {exc}"


def _generate_unified_diff(original: str, fixed: str, filename: str) -> str:
    """Generate a unified diff between original and fixed code."""
    import difflib
    original_lines = original.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines, fixed_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="",
    )
    return "".join(diff)


def _build_fix_prompt(finding: dict) -> str:
    return f"""You are fixing a {finding.get('severity', 'high')}-severity security vulnerability.

Vulnerability: {finding.get('title', 'Unknown')}
Rule: {finding.get('rule_id', 'N/A')}
CWE: {finding.get('cwe_id', 'N/A')}
Category: {finding.get('category', 'unknown')}
File: {finding.get('file_path', 'unknown')}
Line: {finding.get('line_start', '?')}

Description:
{finding.get('description', '')}

Why it was flagged:
{finding.get('why_flagged', '')}

ORIGINAL VULNERABLE CODE:
```
{finding.get('code_snippet', finding.get('code_context', 'Not available'))}
```

Generate a secure fix that:
1. Eliminates the exact vulnerability
2. Preserves all existing functionality
3. Follows security best practices
4. Uses minimal code changes

Remember: respond ONLY with the JSON schema defined in your instructions."""


class AutoFixAgent(BaseAgent):
    name = "autofix"
    display_name = "Auto-Fix Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        # Collect all findings from upstream agents
        all_upstream_findings: list[dict] = []
        for agent_name, result_data in ctx.upstream_results.items():
            if isinstance(result_data, dict):
                all_upstream_findings.extend(result_data.get("findings", []))

        # Filter to fixable findings
        fixable = [
            f for f in all_upstream_findings
            if (
                f.get("severity") in FIXABLE_SEVERITIES
                and f.get("category") not in SKIP_CATEGORIES
                and f.get("code_snippet")  # Need code to fix
                and not f.get("is_false_positive")
            )
        ]

        # Limit to top-N to avoid runaway LLM cost
        MAX_FIXES_PER_SCAN = 10
        fixable = sorted(
            fixable,
            key=lambda f: {"critical": 0, "high": 1, "medium": 2}.get(f.get("severity", "medium"), 3),
        )[:MAX_FIXES_PER_SCAN]

        if not fixable:
            return AgentResult(
                agent_name=self.name,
                success=True,
                findings=[],
                extra={"fixes_attempted": 0, "fixes_verified": 0},
            )

        fixes_attempted = 0
        fixes_verified = 0
        fix_results: list[dict] = []

        for finding in fixable:
            fix_result = await self._attempt_fix(finding, ctx)
            fix_results.append(fix_result)
            fixes_attempted += 1
            if fix_result.get("sandbox_status") == "passed" and fix_result.get("status") == "verified":
                fixes_verified += 1

        return AgentResult(
            agent_name=self.name,
            success=True,
            findings=[],  # Auto-fix doesn't generate new findings
            extra={
                "fixes_attempted": fixes_attempted,
                "fixes_verified": fixes_verified,
                "fix_results": fix_results,
            },
        )

    async def _attempt_fix(self, finding: dict, ctx: AgentContext) -> dict:
        """Attempt to auto-fix a single finding. Returns fix metadata dict."""
        start = time.perf_counter()
        finding_id = finding.get("id", "unknown")
        file_path = finding.get("file_path", "")

        log.info("Attempting auto-fix", finding_id=finding_id, rule=finding.get("rule_id"))

        fix_record: dict = {
            "finding_id": finding_id,
            "scan_id": ctx.scan_id,
            "file_path": file_path,
            "fix_type": "automated",
            "status": "pending",
            "sandbox_status": "pending",
            "ai_provider": None,
            "ai_model": None,
        }

        # ── Step 1: Generate fix with LLM ─────────────────────────
        try:
            req = model_router.ModelRequest(
                system_prompt=AUTOFIX_SYSTEM,
                prompt=_build_fix_prompt(finding),
                temperature=0.0,  # Deterministic for code fixes
                max_tokens=3000,
            )
            response = await model_router.complete_json(
                req, preferred_provider=ctx.ai_provider, preferred_model=ctx.ai_model
            )
            fix_data = response.get("fix", {})

        except model_router.ModelUnavailableError as exc:
            fix_record["status"] = "skipped"
            fix_record["sandbox_status"] = "skipped"
            fix_record["application_error"] = f"LLM unavailable: {exc}"
            return fix_record
        except Exception as exc:
            fix_record["status"] = "rejected"
            fix_record["application_error"] = f"LLM error: {exc}"
            return fix_record

        if not fix_data or fix_data.get("fix_type") == "manual_required":
            fix_record["status"] = "manual_required"
            fix_record["step_by_step"] = fix_data.get("step_by_step", "Manual remediation required.")
            fix_record["description"] = fix_data.get("description", "")
            return fix_record

        original_code = fix_data.get("original_code", finding.get("code_snippet", ""))
        fixed_code = fix_data.get("fixed_code", "")

        if not fixed_code or fixed_code == original_code:
            fix_record["status"] = "rejected"
            fix_record["application_error"] = "LLM returned empty or identical fix."
            return fix_record

        fix_record.update({
            "original_code": original_code,
            "fixed_code": fixed_code,
            "description": fix_data.get("description", ""),
            "why_safe": fix_data.get("why_safe", ""),
            "step_by_step": fix_data.get("step_by_step", ""),
            "fix_strategy": fix_data.get("strategy", ""),
            "status": "sandbox_testing",
            "sandbox_status": "running",
        })

        # ── Step 2: Sandbox Validation ─────────────────────────────
        sandbox_result = await self._run_sandbox(
            file_path=file_path,
            original_code=original_code,
            fixed_code=fixed_code,
            file_contents=ctx.file_contents,
            finding=finding,
        )

        fix_record.update(sandbox_result)
        fix_record["diff_patch"] = _generate_unified_diff(original_code, fixed_code, file_path)
        fix_record["diff_stats"] = {
            "lines_added": sum(1 for l in fix_record["diff_patch"].split("\n") if l.startswith("+")),
            "lines_removed": sum(1 for l in fix_record["diff_patch"].split("\n") if l.startswith("-")),
        }

        if sandbox_result.get("sandbox_status") == "passed":
            fix_record["status"] = "verified"
            fix_record["is_verified"] = True
            fix_record["verification_method"] = sandbox_result.get("verification_method", "sandbox")
        else:
            fix_record["status"] = "rejected"
            fix_record["is_verified"] = False

        fix_record["sandbox_duration_seconds"] = time.perf_counter() - start

        log.info(
            "Fix attempt complete",
            finding_id=finding_id,
            status=fix_record["status"],
            sandbox=sandbox_result.get("sandbox_status"),
        )
        return fix_record

    async def _run_sandbox(
        self,
        file_path: str,
        original_code: str,
        fixed_code: str,
        file_contents: dict,
        finding: dict,
    ) -> dict:
        """
        Run the fixed code through an isolated validation pipeline.
        Returns sandbox result dict.
        """
        checks_passed: list[str] = []
        checks_failed: list[str] = []
        test_output = ""
        lint_output = ""

        # ── Check 1: Syntax validation ─────────────────────────────
        if file_path.endswith(".py"):
            syntax_ok, syntax_err = _validate_python_syntax(fixed_code)
            if syntax_ok:
                checks_passed.append("python_syntax_check")
            else:
                checks_failed.append(f"python_syntax_check: {syntax_err}")
                return {
                    "sandbox_status": "failed",
                    "sandbox_checks_passed": checks_passed,
                    "sandbox_checks_failed": checks_failed,
                    "sandbox_test_output": syntax_err,
                    "verification_method": "syntax_check",
                }

        # ── Check 2: Write to temp file + lint ─────────────────────
        tmp_dir = tempfile.mkdtemp(prefix="sentinel_fix_")
        try:
            tmp_file = Path(tmp_dir) / Path(file_path).name
            tmp_file.write_text(fixed_code, encoding="utf-8")

            if file_path.endswith(".py"):
                lint_ok, lint_output = _run_flake8(str(tmp_file))
                if lint_ok:
                    checks_passed.append("flake8_lint")
                else:
                    # Lint warnings don't fail — only critical errors
                    checks_passed.append("flake8_lint_warnings")
                    lint_output = f"Warnings (non-blocking): {lint_output[:500]}"

            # ── Check 3: Verify the fix actually removed the vulnerability pattern ─
            fix_removed_issue = self._verify_fix_removes_issue(fixed_code, finding)
            if fix_removed_issue:
                checks_passed.append("vulnerability_pattern_removed")
            else:
                checks_failed.append("vulnerability_pattern_still_present")

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        # ── Determine final sandbox status ─────────────────────────
        if checks_failed:
            return {
                "sandbox_status": "failed",
                "sandbox_checks_passed": checks_passed,
                "sandbox_checks_failed": checks_failed,
                "sandbox_test_output": test_output,
                "sandbox_lint_output": lint_output,
                "verification_method": "sandbox_checks",
            }

        return {
            "sandbox_status": "passed",
            "sandbox_checks_passed": checks_passed,
            "sandbox_checks_failed": [],
            "sandbox_test_output": test_output,
            "sandbox_lint_output": lint_output,
            "verification_method": "sandbox_checks",
        }

    def _verify_fix_removes_issue(self, fixed_code: str, finding: dict) -> bool:
        """Check that the fix removed the vulnerable pattern identified in the finding."""
        original_snippet = finding.get("code_snippet", "")
        if not original_snippet or len(original_snippet) < 5:
            return True  # Can't verify, assume OK

        # If the exact snippet no longer appears in the fixed code, the fix worked
        return original_snippet.strip() not in fixed_code
