"""
CodeSentinel — Agent 5: Compliance Enforcement Agent
Checks code changes against SOC2, HIPAA, PCI-DSS 4.0, and GDPR Article 32.
Each framework is implemented as a set of rule packs with real checks.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Optional

import structlog

from app.agents.base_agent import AgentContext, AgentResult, BaseAgent
from app.ai import model_router
from app.ai.prompts.agent_prompts import COMPLIANCE_AGENT_SYSTEM

log = structlog.get_logger("agents.compliance")


@dataclass
class ComplianceRule:
    id: str
    framework: str
    clause: str
    title: str
    check_description: str
    # Regex patterns that trigger a violation
    violation_patterns: list[str]
    # Regex patterns that indicate compliance (if present, reduces false positives)
    safe_patterns: list[str]
    severity: str = "high"
    cvss: float = 6.5


# ── SOC2 Rules ─────────────────────────────────────────────────────────────────
SOC2_RULES: list[ComplianceRule] = [
    ComplianceRule(
        id="SOC2-CC6.1-001",
        framework="soc2",
        clause="CC6.1",
        title="Missing access control — unauthenticated endpoint",
        check_description="API endpoints handling sensitive data must enforce authentication.",
        violation_patterns=[
            r'@app\.route\(["\'][^"\']+["\'][^)]*\)\s*\ndef\s+\w+\s*\([^)]*\):\s*\n(?:(?!\s*(auth|login_required|current_user|jwt_required|require_auth)).)*(?:db\.|query|execute|DELETE|UPDATE|INSERT)',
        ],
        safe_patterns=[r'login_required', r'jwt_required', r'@require_auth', r'current_user'],
        severity="critical",
        cvss=9.1,
    ),
    ComplianceRule(
        id="SOC2-CC6.2-001",
        framework="soc2",
        clause="CC6.2",
        title="Weak password policy — insufficient complexity enforcement",
        check_description="SOC2 requires enforcing strong password policies in authentication code.",
        violation_patterns=[
            r'len\(password\)\s*[<>]=?\s*[1-7]\b',
            r'min_length\s*=\s*[1-7]\b',
        ],
        safe_patterns=[r'len\(password\)\s*[<>]=?\s*[89]', r'len\(password\)\s*[<>]=?\s*1[0-9]'],
        severity="medium",
        cvss=5.0,
    ),
    ComplianceRule(
        id="SOC2-CC7.1-001",
        framework="soc2",
        clause="CC7.1",
        title="Missing security event logging",
        check_description="Authentication failures, access denials, and sensitive operations must be logged.",
        violation_patterns=[
            r'except\s+(AuthenticationError|PermissionDenied|Unauthorized).*:\s*\n\s*(pass|return|raise)\s*$',
        ],
        safe_patterns=[r'logging\.', r'log\.', r'logger\.', r'audit_log'],
        severity="medium",
        cvss=4.5,
    ),
]

# ── HIPAA Rules ────────────────────────────────────────────────────────────────
HIPAA_RULES: list[ComplianceRule] = [
    ComplianceRule(
        id="HIPAA-164.312a2iv-001",
        framework="hipaa",
        clause="164.312(a)(2)(iv)",
        title="ePHI not encrypted at rest",
        check_description="Electronic Protected Health Information must be encrypted when stored.",
        violation_patterns=[
            r'(?i)(medical|health|patient|diagnosis|treatment|prescription|ssn)\s*=\s*(?!encrypt|cipher|hash)',
            r'db\.Column\s*\([^)]*String[^)]*\).*#.*(?i)(health|patient|phi|medical)',
        ],
        safe_patterns=[r'encrypt', r'Fernet', r'AES', r'cipher', r'pgcrypto'],
        severity="critical",
        cvss=8.7,
    ),
    ComplianceRule(
        id="HIPAA-164.312e2ii-001",
        framework="hipaa",
        clause="164.312(e)(2)(ii)",
        title="ePHI transmitted without TLS enforcement",
        check_description="ePHI in transit must be protected with TLS 1.2 or higher.",
        violation_patterns=[
            r'verify\s*=\s*False',
            r'ssl\s*=\s*False',
            r'http://',
        ],
        safe_patterns=[r'https://', r'verify=True', r'ssl=True', r'tls_version'],
        severity="high",
        cvss=7.4,
    ),
    ComplianceRule(
        id="HIPAA-164.312d-001",
        framework="hipaa",
        clause="164.312(d)",
        title="Authentication identity not verified before ePHI access",
        check_description="All systems accessing ePHI must authenticate users before granting access.",
        violation_patterns=[
            r'(?i)(patient|health_record|medical_history|prescription).*(?:get|post|put|delete).*(?:def\s+\w+\s*\([^)]*\):)',
        ],
        safe_patterns=[r'@login_required', r'@jwt_required', r'authenticate', r'current_user'],
        severity="critical",
        cvss=9.0,
    ),
]

# ── PCI-DSS Rules ─────────────────────────────────────────────────────────────
PCI_DSS_RULES: list[ComplianceRule] = [
    ComplianceRule(
        id="PCI-6.3.1-001",
        framework="pci_dss",
        clause="6.3.1",
        title="SQL injection vulnerability in payment code",
        check_description="PCI-DSS requires protection against SQL injection in all code handling cardholder data.",
        violation_patterns=[
            r'(?i)(card|payment|transaction|cardholder).*(?:execute|query|cursor)\s*\(\s*[f"\'].*%s|format|f-string',
            r'(?i)SELECT.*\+.*(?:card|payment|amount)',
        ],
        safe_patterns=[r'parameterized', r'prepared', r'\?', r'%s.*\('],
        severity="critical",
        cvss=9.8,
    ),
    ComplianceRule(
        id="PCI-8.3.6-001",
        framework="pci_dss",
        clause="8.3.6",
        title="Insufficient password complexity for cardholder data system",
        check_description="PCI-DSS requires passwords of at least 12 characters with complexity.",
        violation_patterns=[
            r'min_length\s*=\s*[1-9]\b',
            r'len\(password\)\s*<\s*(?:[1-9]|1[01])\b',
        ],
        safe_patterns=[r'min_length\s*=\s*1[2-9]', r'len\(password\)\s*<\s*1[2-9]'],
        severity="high",
        cvss=6.5,
    ),
    ComplianceRule(
        id="PCI-6.4.1-001",
        framework="pci_dss",
        clause="6.4.1",
        title="Missing input validation on payment data fields",
        check_description="All payment card data fields must be validated before processing.",
        violation_patterns=[
            r'(?i)(card_number|cvv|expiry|cardholder_name)\s*=\s*request\.(json|form|args)\[',
        ],
        safe_patterns=[r'validate', r'sanitize', r'clean', r'Validator', r'Schema'],
        severity="high",
        cvss=7.5,
    ),
]

# ── GDPR Rules ─────────────────────────────────────────────────────────────────
GDPR_RULES: list[ComplianceRule] = [
    ComplianceRule(
        id="GDPR-32-001",
        framework="gdpr",
        clause="Article 32",
        title="Personal data processed without encryption",
        check_description="GDPR Article 32 requires appropriate technical measures including encryption of personal data.",
        violation_patterns=[
            r'(?i)(email|phone|address|name|dob|birth|passport|ssn|national_id)\s*=\s*(?!encrypt|hash)',
        ],
        safe_patterns=[r'encrypt', r'hash', r'anonymize', r'pseudonymize'],
        severity="high",
        cvss=6.8,
    ),
    ComplianceRule(
        id="GDPR-32-002",
        framework="gdpr",
        clause="Article 32",
        title="No data retention control — personal data stored indefinitely",
        check_description="GDPR requires personal data not be retained longer than necessary.",
        violation_patterns=[
            r'(?i)(user|customer|personal).*model.*(?!deleted_at|expires_at|retention|purge)',
        ],
        safe_patterns=[r'deleted_at', r'expires_at', r'retention_days', r'purge_after'],
        severity="medium",
        cvss=4.3,
    ),
    ComplianceRule(
        id="GDPR-32-003",
        framework="gdpr",
        clause="Article 32",
        title="Personal data logged without masking",
        check_description="GDPR prohibits logging personal data in plain text where not necessary.",
        violation_patterns=[
            r'(?i)log\w*\s*\([^)]*(?:email|password|phone|address|ssn|dob)[^)]*\)',
            r'(?i)print\s*\([^)]*(?:email|password|phone|address)[^)]*\)',
        ],
        safe_patterns=[r'masked', r'\*\*\*', r'redact', r'anonymize'],
        severity="medium",
        cvss=5.0,
    ),
]

ALL_RULES = {
    "soc2": SOC2_RULES,
    "hipaa": HIPAA_RULES,
    "pci_dss": PCI_DSS_RULES,
    "gdpr": GDPR_RULES,
}


def _compile_pattern(pattern: str) -> Optional[re.Pattern[str]]:
    """Compile regex robustly, recovering from misplaced inline flags."""
    try:
        return re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    except re.error:
        cleaned = re.sub(r"\(\?[aiLmsux-]+\)", "", pattern)
        try:
            return re.compile(cleaned, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        except re.error:
            return None


def _check_rule_in_content(rule: ComplianceRule, content: str, file_path: str) -> Optional[dict]:
    """Check a single compliance rule against file content using regex patterns."""
    lines = content.split("\n")
    for pattern in rule.violation_patterns:
        compiled = _compile_pattern(pattern)
        if not compiled:
            log.warning("Skipping invalid compliance pattern", rule_id=rule.id, pattern=pattern)
            continue

        for match in compiled.finditer(content):
            line_start = content.count("\n", 0, match.start()) + 1
            line_end = content.count("\n", 0, match.end()) + 1
            idx = max(0, line_start - 1)
            line = lines[idx] if idx < len(lines) else ""

            # Check safe patterns in nearby context to reduce false positives.
            context = "\n".join(lines[max(0, line_start - 4):min(len(lines), line_end + 3)])
            safe_present = False
            for safe in rule.safe_patterns:
                safe_compiled = _compile_pattern(safe)
                if safe_compiled and safe_compiled.search(context):
                    safe_present = True
                    break
            if safe_present:
                continue

            fp_input = f"{rule.id}:{file_path}:{line_start}"
            return {
                "rule_id": rule.id,
                "title": rule.title,
                "description": rule.check_description,
                "why_flagged": (
                    f"Compliance rule {rule.id} ({rule.clause}) was triggered by a pattern match at {file_path}:{line_start}. "
                    f"{rule.check_description} The matched pattern suggests {rule.title.lower()}."
                ),
                "business_risk": (
                    f"This {rule.framework.upper()} violation ({rule.clause}: {rule.title}) may result in "
                    f"regulatory penalties, audit failures, or data breach liability. "
                    f"GDPR fines can reach EUR 20M or 4% of global turnover. PCI-DSS violations can result in fines of $5,000 to $100,000 per month."
                ),
                "recommendation": f"Remediate to comply with {rule.framework.upper()} {rule.clause}: {rule.check_description}",
                "file_path": file_path,
                "line_start": line_start,
                "line_end": line_end,
                "code_snippet": line.strip(),
                "severity": rule.severity,
                "cvss_score": rule.cvss,
                "confidence": "medium",
                "category": "compliance",
                "agent_type": "compliance",
                "compliance_frameworks": [f"{rule.framework}:{rule.clause}"],
                "compliance_details": {
                    "framework": rule.framework,
                    "clause": rule.clause,
                    "requirement": rule.check_description,
                    "rule_id": rule.id,
                },
                "fingerprint": hashlib.sha256(fp_input.encode()).hexdigest()[:16],
                "fix_available": False,
                "fix_complexity": "moderate",
            }
    return None


class ComplianceAgent(BaseAgent):
    name = "compliance"
    display_name = "Compliance Enforcement Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        all_findings: list[dict] = []
        compliance_results: dict[str, dict] = {}
        analysis_summary = "Rule-based compliance checks executed successfully."
        tokens_used = 0
        ai_provider = None
        ai_model = None

        active_profiles = ctx.compliance_profiles or list(ALL_RULES.keys())
        # Default to checking all frameworks if none configured
        profiles_to_check = [p for p in active_profiles if p in ALL_RULES]
        if not profiles_to_check:
            profiles_to_check = list(ALL_RULES.keys())

        # ── Phase 1: Rule-based regex checks (fast, no LLM) ────────
        for profile in profiles_to_check:
            rules = ALL_RULES[profile]
            passed = 0
            failed = 0
            profile_findings: list[dict] = []

            for rule in rules:
                rule_violated = False
                for file_path, content in ctx.file_contents.items():
                    if not content:
                        continue
                    finding = _check_rule_in_content(rule, content, file_path)
                    if finding:
                        profile_findings.append(finding)
                        rule_violated = True
                        break
                if rule_violated:
                    failed += 1
                else:
                    passed += 1

            total = passed + failed
            score = int((passed / total) * 100) if total > 0 else 100
            compliance_results[profile] = {
                "passed": passed,
                "failed": failed,
                "score": score,
                "findings_count": len(profile_findings),
            }
            all_findings.extend(profile_findings)

        # ── Phase 2: LLM-based compliance review for nuanced checks ─
        llm_input = ctx.diff_content[:6000] if ctx.diff_content else ""
        if not llm_input.strip() and ctx.file_contents:
            chunks: list[str] = []
            budget = 6000
            for path, content in list(ctx.file_contents.items())[:8]:
                if not content:
                    continue
                block = f"--- {path} ---\n{content[:1200]}\n"
                if len(block) > budget:
                    break
                chunks.append(block)
                budget -= len(block)
                if budget < 300:
                    break
            llm_input = "\n".join(chunks)

        if llm_input.strip():
            try:
                profiles_str = ", ".join(p.upper().replace("_", "-") for p in profiles_to_check)
                req = model_router.ModelRequest(
                    system_prompt=COMPLIANCE_AGENT_SYSTEM,
                    prompt=f"""Review this code diff for compliance violations.
Active compliance frameworks: {profiles_str}

CODE INPUT:
{llm_input}

Rule-based analysis already found {len(all_findings)} potential violations.
Identify any additional compliance issues that pattern matching may have missed.
Focus on semantic compliance gaps — missing audit trails, improper data handling, insecure defaults.""",
                    temperature=0.05,
                    max_tokens=3000,
                )
                response = await model_router.complete_json(
                    req, preferred_provider=ctx.ai_provider, preferred_model=ctx.ai_model
                )
                llm_findings = response.get("findings", [])
                llm_scores = response.get("compliance_scores", {})

                for f in llm_findings:
                    if not f.get("title"):
                        continue
                    f.setdefault("agent_type", "compliance")
                    f.setdefault("category", "compliance")
                    f.setdefault("fingerprint", hashlib.sha256(
                        f"{f.get('rule_id', '')}:{f.get('file_path', '')}:{f.get('title', '')}".encode()
                    ).hexdigest()[:16])
                    all_findings.append(f)

                tokens_used = response.get("_tokens", 0)
                ai_provider = response.get("_provider")
                ai_model = response.get("_model")
                analysis_summary = response.get("analysis_summary", analysis_summary)

                # Merge LLM scores into rule-based scores
                for profile, llm_score in llm_scores.items():
                    if profile in compliance_results:
                        compliance_results[profile]["llm_notes"] = llm_score.get("notes", "")
                    else:
                        compliance_results[profile] = llm_score

            except model_router.ModelUnavailableError as exc:
                log.warning("Compliance LLM review skipped — no provider available", error=str(exc))
                analysis_summary = f"LLM compliance review unavailable: {exc}. Returned rule-based compliance checks only."
            except Exception as exc:
                log.error("Compliance LLM review error", error=str(exc))
                analysis_summary = f"LLM compliance review failed with error: {exc}. Returned rule-based compliance checks only."

        log.info(
            "Compliance check complete",
            scan_id=ctx.scan_id,
            findings=len(all_findings),
            profiles=profiles_to_check,
        )

        return AgentResult(
            agent_name=self.name,
            success=True,
            findings=all_findings,
            tokens_used=tokens_used,
            ai_provider=ai_provider,
            ai_model=ai_model,
            extra={
                "compliance_results": compliance_results,
                "profiles_checked": profiles_to_check,
                "analysis_summary": analysis_summary,
                "llm_enabled": True,
                "llm_provider": ai_provider,
                "llm_model": ai_model,
            },
        )
