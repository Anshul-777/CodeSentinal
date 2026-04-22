"""
CodeSentinel — Agent 1: Static Analysis + Semantic Vulnerability Scanner
Combines:
  1. Bandit (Python AST-based security linter) — real tool, real output
  2. Custom AST pattern scanner for language-agnostic patterns
  3. LLM semantic analysis for context-aware vulnerabilities that static tools miss
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Optional

import structlog

from app.agents.base_agent import AgentContext, AgentResult, BaseAgent
from app.ai import model_router
from app.ai.prompts.agent_prompts import STATIC_ANALYSIS_SYSTEM

log = structlog.get_logger("agents.static")

# ── Secret patterns for the static layer (agent 5 does deeper compliance) ─────
SECRET_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, secret_type, description)
    (r'(?i)(aws_access_key_id|aws_secret_access_key)\s*[=:]\s*["\']?([A-Z0-9/+]{20,40})', "aws_credential", "AWS credential"),
    (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']([a-zA-Z0-9_\-]{20,80})["\']', "api_key", "Generic API key"),
    (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']([^"\']{8,})["\']', "hardcoded_password", "Hardcoded password"),
    (r'ghp_[a-zA-Z0-9]{16,}', "github_pat", "GitHub personal access token"),
    (r'ghs_[a-zA-Z0-9]{16,}', "github_actions_token", "GitHub Actions token"),
    (r'(?i)\b(token|access[_-]?token|auth[_-]?token)\b\s*[=:]\s*["\']([a-zA-Z0-9_\-]{12,})["\']', "generic_token", "Generic access token"),
    (r'sk-[a-zA-Z0-9]{48}', "openai_key", "OpenAI API key"),
    (r'sk_live_[a-zA-Z0-9]{24,}', "stripe_live_key", "Stripe live secret key"),
    (r'(?i)(jwt[_-]?secret|jwt[_-]?key)\s*[=:]\s*["\']([^"\']{10,})["\']', "jwt_secret", "JWT secret"),
    (r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----', "private_key", "Private key in source"),
    (r'(?i)mongodb(\+srv)?://[^:]+:[^@]+@', "mongodb_uri", "MongoDB connection string with credentials"),
    (r'(?i)postgres(ql)?://[^:]+:[^@]+@', "postgres_uri", "PostgreSQL connection string with credentials"),
    (r'(?i)mysql://[^:]+:[^@]+@', "mysql_uri", "MySQL connection string with credentials"),
    (r'AIza[0-9A-Za-z\-_]{35}', "google_api_key", "Google API key"),
    (r'(?i)(twilio[_-]?auth[_-]?token)\s*[=:]\s*["\']([a-f0-9]{32})["\']', "twilio_token", "Twilio auth token"),
    (r'(?i)(sendgrid[_-]?api[_-]?key)\s*[=:]\s*["\']SG\.', "sendgrid_key", "SendGrid API key"),
    (r'xox[bpoa]-[0-9]{12}-[0-9]{12}-[a-zA-Z0-9]{24}', "slack_token", "Slack token"),
]

# ── Dangerous function patterns across languages ────────────────────────────
DANGEROUS_PATTERNS: list[tuple[str, str, str, str, float]] = [
    # (pattern, rule_id, title, category, cvss)
    (r'\beval\s*\(', "STATIC-EVAL-001", "Use of eval() with possible user input", "injection", 8.8),
    (r'\bexec\s*\(', "STATIC-EXEC-001", "Use of exec() — code execution risk", "injection", 8.8),
    (r'\bos\.system\s*\(', "STATIC-CMDINJECT-001", "os.system() call — command injection risk", "injection", 9.0),
    (r'\bsubprocess\.(call|run|Popen)\s*\([^)]*shell\s*=\s*True', "STATIC-CMDINJECT-002", "subprocess with shell=True", "injection", 9.0),
    (r'pickle\.(loads|load)\s*\(', "STATIC-DESER-001", "Unsafe pickle deserialization", "deserialization", 8.1),
    (r'yaml\.load\s*\([^,)]+\)', "STATIC-DESER-002", "yaml.load() without Loader — arbitrary code execution", "deserialization", 8.8),
    (r'hashlib\.(md5|sha1)\s*\(', "STATIC-CRYPTO-001", "Use of weak hash algorithm (MD5/SHA1)", "crypto", 5.3),
    (r'random\.(random|randint|choice)\s*\(', "STATIC-CRYPTO-002", "Use of non-cryptographic random for security context", "crypto", 6.5),
    (r'\b(?:cursor\.)?execute\s*\(\s*f["\']', "STATIC-SQLI-001", "SQL query built with f-string", "injection", 9.1),
    (r'\b(?:cursor\.)?execute\s*\(\s*["\'][^"\']*(SELECT|INSERT|UPDATE|DELETE)[^"\']*\{', "STATIC-SQLI-002", "SQL query built with string interpolation", "injection", 9.0),
    (r'SSL_VERIFY\s*=\s*False|verify\s*=\s*False', "STATIC-TLS-001", "TLS/SSL verification disabled", "crypto", 7.4),
    (r'DEBUG\s*=\s*True', "STATIC-CONFIG-001", "Debug mode enabled — may expose stack traces", "config", 5.3),
    (r'\bSECRET_KEY\s*=\s*["\'][^"\']{1,20}["\']', "STATIC-SECRET-001", "Short or default SECRET_KEY", "secrets", 7.5),
    (r'render_template_string\s*\(\s*template\s*\)', "STATIC-SSTI-001", "Potential Server-Side Template Injection", "injection", 9.0),
    (r'(?i)render_template_string\s*\(.*?(?:f"|\'|\.format|%|str\(|var|arg|\+)', "STATIC-SSTI-003", "Potential Server-Side Template Injection", "injection", 9.0),
    (r'(?i)(?:os|subprocess)\.(?:system|popen|run|call|check_output)\s*\(.*?(?:f"|\'|\.format|%|str\(|var|arg|\+|\w+)', "STATIC-CMDINJECT-005", "Command injection risk", "injection", 9.0),
    (r'(?i)(?:cursor|conn|db)\.execute\s*\(.*?(?:f"|\.format|%|\+)', "STATIC-SQLI-003", "SQL injection risk", "injection", 9.0),
    (r'\bsubprocess\.(run|call|Popen)\s*\([^)]*(request\.(args|form|values|get_json)|input\s*\()', "STATIC-CMDINJECT-004", "subprocess call uses likely user-controlled input", "injection", 9.0),
    (r'__import__\s*\(', "STATIC-IMPORT-001", "Dynamic __import__() usage", "injection", 7.2),
    (r'open\s*\([^)]*["\'][rwab]{1,3}["\']', "STATIC-PATH-001", "File open — verify path is not user-controlled", "path_traversal", 5.5),
    (r'\b(query|sql)\s*=\s*f?["\'].*\{.*\}', "STATIC-SQLI-003", "Latent SQL injection — query built with interpolation", "injection", 8.5),
    (r'\b(cmd|command)\s*=\s*f?["\'].*\{.*\}', "STATIC-CMDINJECT-005", "Latent command injection — command string built with interpolation", "injection", 8.5),
]


def _safe_compile_regex(pattern: str) -> Optional[re.Pattern[str]]:
    """Compile regex safely; recover from misplaced inline flags like (?i) in the middle."""
    try:
        return re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error:
        cleaned = re.sub(r"\(\?[aiLmsux-]+\)", "", pattern)
        try:
            return re.compile(cleaned, re.IGNORECASE | re.MULTILINE)
        except re.error:
            return None


def _run_bandit_on_python(code: str, filename: str) -> list[dict]:
    """Run Bandit on Python code and return structured findings."""
    findings = []
    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        result = subprocess.run(
            ["bandit", "-f", "json", "-q", tmp_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        os.unlink(tmp_path)

        if result.stdout:
            try:
                data = json.loads(result.stdout)
                for issue in data.get("results", []):
                    findings.append({
                        "rule_id": f"BANDIT-{issue['test_id']}",
                        "cwe_id": None,
                        "title": issue["issue_text"],
                        "description": f"{issue['issue_text']}. Bandit test: {issue['test_name']}.",
                        "file_path": filename,
                        "line_start": issue["line_number"],
                        "line_end": issue.get("line_range", [issue["line_number"]])[-1],
                        "code_snippet": issue.get("code", ""),
                        "severity": _map_bandit_severity(issue["issue_severity"]),
                        "cvss_score": _bandit_severity_to_cvss(issue["issue_severity"], issue["issue_confidence"]),
                        "confidence": issue["issue_confidence"].lower(),
                        "category": "static_analysis",
                        "why_flagged": f"Bandit rule {issue['test_id']} ({issue['test_name']}) detected this pattern. "
                                       f"Severity: {issue['issue_severity']}, Confidence: {issue['issue_confidence']}.",
                        "business_risk": _generate_business_risk(issue["test_id"], issue["issue_severity"]),
                        "recommendation": f"Review and remediate: {issue['issue_text']}. See https://bandit.readthedocs.io/en/latest/plugins/{issue['test_id'].lower()}.html",
                        "references": [f"https://bandit.readthedocs.io/en/latest/plugins/{issue['test_id'].lower()}.html"],
                        "source": "bandit",
                    })
            except (json.JSONDecodeError, KeyError):
                pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Bandit not installed or timeout — continue with regex scanner
        pass
    return findings


def _map_bandit_severity(sev: str) -> str:
    return {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}.get(sev.upper(), "info")


def _bandit_severity_to_cvss(severity: str, confidence: str) -> float:
    base = {"HIGH": 7.5, "MEDIUM": 5.0, "LOW": 2.5}.get(severity.upper(), 2.0)
    modifier = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.6}.get(confidence.upper(), 0.7)
    return round(min(base * modifier + 0.5, 10.0), 1)


def _generate_business_risk(test_id: str, severity: str) -> str:
    risks = {
        "B105": "Hardcoded passwords allow unauthorized access to systems, leading to data breaches and compliance violations.",
        "B106": "Hardcoded passwords in function arguments expose credentials if code is shared or version-controlled.",
        "B107": "Hardcoded passwords in function defaults are a persistent security risk across all deployments.",
        "B201": "Flask debug mode enabled in production exposes an interactive debugger — attackers can execute arbitrary code.",
        "B301": "Pickle deserialization of untrusted data allows arbitrary code execution, leading to complete system compromise.",
        "B302": "yaml.load() without a safe Loader allows arbitrary code execution when parsing untrusted YAML input.",
        "B303": "MD5 is a broken hash algorithm — collision attacks can allow attackers to forge authentication tokens.",
        "B304": "DES/3DES are deprecated cipher suites with known weaknesses enabling decryption of protected data.",
        "B501": "TLS certificate verification disabled — opens connections to man-in-the-middle attacks intercepting sensitive data.",
        "B602": "Shell injection via subprocess allows attackers to execute arbitrary OS commands if user input reaches this call.",
        "B603": "subprocess call without shell=True is safer but still needs input validation to prevent argument injection.",
        "B604": "Function with shell=True parameter is a command injection risk if any argument contains user-controlled data.",
        "B608": "SQL query constructed with string formatting — SQL injection can expose or destroy the entire database.",
    }
    default = f"This {severity.lower()}-severity finding represents a real attack vector that, if exploited, could lead to data breach, system compromise, or regulatory non-compliance."
    return risks.get(test_id, default)


def _safe_compile_regex(pattern: str) -> Optional[re.Pattern[str]]:
    """Compile regex robustly, removing misplaced inline flags like (?i) for Python 3.11+."""
    try:
        # Remove mid-string inline flags: converting `(?i)` to global `re.IGNORECASE`
        cleaned = re.sub(r'\(\?[imsux-]+\)', '', pattern)
        return re.compile(cleaned, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    except re.error as exc:
        log.error("Failed to compile pattern", pattern=pattern, error=str(exc))
        try:
            return re.compile(pattern, re.IGNORECASE)
        except re.error:
            return None


def _scan_with_regex(code: str, filename: str) -> list[dict]:
    """Regex-based scanner for cross-language dangerous patterns."""
    findings = []
    lines = code.split("\n")

    for pattern, rule_id, title, category, cvss in DANGEROUS_PATTERNS:
        compiled = _safe_compile_regex(pattern)
        if not compiled:
            continue

        seen_lines: set[int] = set()
        for match in compiled.finditer(code):
            i = code.count("\n", 0, match.start()) + 1
            if i in seen_lines:
                continue
            seen_lines.add(i)
            line = lines[i - 1] if 0 <= i - 1 < len(lines) else ""
            findings.append({
                "rule_id": rule_id,
                "title": title,
                "description": f"Pattern detected: {title}. Line content: {line.strip()[:200]}",
                "file_path": filename,
                "line_start": i,
                "line_end": i,
                "code_snippet": line.strip(),
                "severity": _cvss_to_severity(cvss),
                "cvss_score": cvss,
                "confidence": "medium",
                "category": category,
                "why_flagged": f"The regex pattern for '{rule_id}' matched this line. {title}.",
                "business_risk": _generate_business_risk(rule_id.split("-")[1] if "-" in rule_id else rule_id, _cvss_to_severity(cvss)),
                "recommendation": "Review this code for security implications. If user input can reach this call, sanitize and validate it first.",
                "references": [],
                "source": "regex",
            })

    return findings


def _build_semantic_payload(ctx: AgentContext) -> str:
    """Build semantic analysis input for both PR and manual scans."""
    if ctx.diff_content and len(ctx.diff_content.strip()) > 50:
        return f"DIFF:\n{ctx.diff_content[:15000]}"

    chunks: list[str] = []
    budget = 15000
    # Prioritize likely source files
    likely_files = sorted(
        ctx.file_contents.items(),
        key=lambda x: (not x[0].endswith((".py", ".js", ".ts", ".go")), x[0])
    )
    
    for path, content in likely_files[:15]:
        if not content:
            continue
        block = f"--- PATH: {path} ---\n{content[:3000]}\n"
        if len(block) > budget:
            # Try to get at least the first part of the file
            block = f"--- PATH: {path} (partial) ---\n{content[:budget]}\n"
            chunks.append(block)
            break
        chunks.append(block)
        budget -= len(block)
        if budget < 500:
            break

    return "CODE REPOSITORY CONTEXT:\n" + "\n".join(chunks)


def _scan_secrets(code: str, filename: str) -> list[dict]:
    """Scan for hardcoded secrets and credentials."""
    findings = []
    lines = code.split("\n")

    for pattern, secret_type, description in SECRET_PATTERNS:
        for i, line in enumerate(lines, 1):
            # Skip comment lines
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                continue
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                matched_val = match.group(0)
                masked = matched_val[:4] + "..." + matched_val[-4:] if len(matched_val) > 8 else "****"
                findings.append({
                    "rule_id": f"SECRET-{secret_type.upper()}-001",
                    "title": f"Hardcoded {description} detected",
                    "description": f"A {description} appears to be hardcoded in source code at {filename}:{i}. Value: {masked}",
                    "file_path": filename,
                    "line_start": i,
                    "line_end": i,
                    "code_snippet": line.strip()[:200],
                    "severity": "critical",
                    "cvss_score": 9.1,
                    "confidence": "high",
                    "category": "secrets",
                    "secret_type": secret_type,
                    "why_flagged": f"The pattern for a {description} matched. Hardcoded secrets in source code are exposed to anyone with repository access and are permanently stored in git history.",
                    "business_risk": f"If this {description} is valid, attackers with repository access can use it to access protected systems, incur charges, or exfiltrate data. Git history must be purged even after removal.",
                    "recommendation": f"1. Immediately revoke this {description}. 2. Remove it from the code and git history using git-filter-repo or BFG Repo Cleaner. 3. Store it in environment variables or a secrets manager (Vault, AWS Secrets Manager).",
                    "references": ["https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository"],
                    "agent_type": "secret",
                    "source": "secret_scanner",
                })

    return findings


def _build_fingerprint(rule_id: str, file_path: str, line: int, snippet: str) -> str:
    content = f"{rule_id}:{file_path}:{line}:{snippet[:100]}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _cvss_to_severity(score: float) -> str:
    if score >= 9.0:
        return "critical"
    elif score >= 7.0:
        return "high"
    elif score >= 4.0:
        return "medium"
    elif score > 0:
        return "low"
    return "info"


class StaticAnalysisAgent(BaseAgent):
    name = "static"
    display_name = "Static Analysis + Semantic Scanner"

    async def run(self, ctx: AgentContext) -> AgentResult:
        all_findings: list[dict] = []
        tokens_used = 0
        ai_provider = None
        ai_model = None
        analysis_summary = "Tool-based static analysis completed."

        # ── Phase 1: Tool-based analysis per file ──────────────────
        python_files: dict[str, str] = {}
        for path, content in ctx.file_contents.items():
            if not content or len(content.strip()) < 10:
                continue

            # Run Bandit on Python files
            if path.endswith(".py"):
                python_files[path] = content
                bandit_findings = _run_bandit_on_python(content, path)
                all_findings.extend(bandit_findings)

            # Run regex scanner on all files
            regex_findings = _scan_with_regex(content, path)
            all_findings.extend(regex_findings)

            # Secret scanning on all files
            secret_findings = _scan_secrets(content, path)
            all_findings.extend(secret_findings)

        # ── Phase 2: LLM semantic analysis on diff/files ───────────
        semantic_input = _build_semantic_payload(ctx)
        if semantic_input.strip() and semantic_input.strip() != "CHANGED FILES:":
            try:
                req = model_router.ModelRequest(
                    system_prompt=STATIC_ANALYSIS_SYSTEM,
                    prompt=f"""Analyze this code diff for security vulnerabilities. Apply your deep reasoning — look for semantic issues that static tools miss.

Repository: {ctx.repo_full_name}
Language: {ctx.repo_language or 'unknown'}

CODE INPUT:
{semantic_input}

Previously detected by static tools (do not duplicate, but you may add context):
{json.dumps([f['rule_id'] for f in all_findings], indent=2)[:500]}

Now perform your semantic analysis:""",
                    temperature=0.05,
                    max_tokens=4096,
                )
                response = await model_router.complete_json(req, preferred_provider=ctx.ai_provider, preferred_model=ctx.ai_model)
                llm_findings = response.get("findings", [])
                for f in llm_findings:
                    f["source"] = "llm_semantic"
                    f["agent_type"] = "static"
                all_findings.extend(llm_findings)
                tokens_used = response.get("_tokens", 0)
                ai_provider = response.get("_provider")
                ai_model = response.get("_model")
                analysis_summary = response.get("analysis_summary", analysis_summary)

                # ── Phase 2b: Additional Secrets Check ───────
                if response.get("secrets"):
                    for s in response["secrets"]:
                        s["source"] = "llm_secret"
                        s["agent_type"] = "static"
                        all_findings.append(s)

            except model_router.ModelUnavailableError as exc:
                log.warning("LLM unavailable for semantic analysis — static tool results still valid", error=str(exc))
                # Do NOT fail the whole agent — Bandit + regex results are still real and useful
                analysis_summary = f"LLM semantic pass unavailable: {exc}. Returned deterministic static results only."
            except Exception as exc:
                log.error("LLM semantic analysis error", error=str(exc))
                analysis_summary = f"LLM semantic pass failed with error: {exc}. Returned deterministic static results only."

        # ── Phase 3: Deduplicate and enrich ────────────────────────
        seen_fingerprints: set[str] = set()
        deduplicated: list[dict] = []

        for finding in all_findings:
            fp = _build_fingerprint(
                finding.get("rule_id", ""),
                finding.get("file_path", ""),
                finding.get("line_start", 0),
                finding.get("code_snippet", ""),
            )
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)

            # Ensure required fields
            finding.setdefault("agent_type", "static")
            finding.setdefault("fingerprint", fp)
            finding.setdefault("fix_available", self._has_auto_fix(finding.get("rule_id", "")))
            finding.setdefault("compliance_frameworks", [])
            finding.setdefault("confidence", "medium")
            deduplicated.append(finding)

        log.info(
            "Static analysis complete",
            scan_id=ctx.scan_id,
            total=len(deduplicated),
            python_files=len(python_files),
        )

        return AgentResult(
            agent_name=self.name,
            success=True,
            findings=deduplicated,
            tokens_used=tokens_used,
            ai_provider=ai_provider,
            ai_model=ai_model,
            extra={
                "files_analyzed": list(ctx.file_contents.keys()),
                "analysis_summary": analysis_summary,
                "llm_enabled": True,
                "llm_provider": ai_provider,
                "llm_model": ai_model,
            },
        )

    def _has_auto_fix(self, rule_id: str) -> bool:
        """Return True for rule IDs that the auto-fix agent can handle."""
        fixable_prefixes = [
            "BANDIT-B301", "BANDIT-B302", "BANDIT-B303", "BANDIT-B501",
            "STATIC-SECRET", "STATIC-CRYPTO", "STATIC-TLS", "STATIC-CONFIG",
            "SECRET-",
        ]
        return any(rule_id.startswith(p) for p in fixable_prefixes)
