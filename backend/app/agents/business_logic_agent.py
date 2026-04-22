"""
CodeSentinel — Agent 3: Business Logic Review Agent
LLM-powered semantic analysis that reads code the way a senior security engineer does —
catching auth bypasses, IDOR, race conditions, validation gaps, and business rule violations
that static regex tools will never find.
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

import structlog

from app.agents.base_agent import AgentContext, AgentResult, BaseAgent
from app.ai import model_router
from app.ai.prompts.agent_prompts import BUSINESS_LOGIC_SYSTEM

log = structlog.get_logger("agents.business_logic")

# Maximum total characters to send to the LLM for business logic review
MAX_CODE_CONTEXT = 12000


def _build_review_prompt(ctx: AgentContext) -> str:
    parts = [f"Repository: {ctx.repo_full_name}", f"Language: {ctx.repo_language or 'unknown'}", ""]

    # Include the diff first as the primary artifact
    if ctx.diff_content:
        parts.append("== CODE DIFF (primary review target) ==")
        parts.append(ctx.diff_content[:MAX_CODE_CONTEXT // 2])
        parts.append("")

    # Include changed file contents for full context
    remaining = MAX_CODE_CONTEXT - sum(len(p) for p in parts)
    if remaining > 500 and ctx.file_contents:
        parts.append("== CHANGED FILE CONTENTS (for context) ==")
        for path, content in list(ctx.file_contents.items())[:5]:
            chunk = content[:min(remaining // max(len(ctx.file_contents), 1), 3000)]
            parts.append(f"--- {path} ---")
            parts.append(chunk)
            remaining -= len(chunk)
            if remaining < 200:
                break

    parts.append("")
    parts.append("Analyze the code above for business logic vulnerabilities. Focus especially on:")
    parts.append("1. Authentication and authorization enforcement")
    parts.append("2. Input validation at trust boundaries")
    parts.append("3. Resource ownership checks (IDOR)")
    parts.append("4. Financial/transactional logic errors")
    parts.append("5. API contract violations")
    parts.append("6. Data exposure through API responses")
    parts.append("")
    parts.append("For each finding, provide the exact file path and line number. Be specific.")

    return "\n".join(parts)


class BusinessLogicAgent(BaseAgent):
    name = "business_logic"
    display_name = "Business Logic Review Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        # If no meaningful code to analyze, skip
        if not ctx.diff_content and not ctx.file_contents:
            return AgentResult(
                agent_name=self.name,
                success=True,
                findings=[],
                extra={"skipped": True, "reason": "No code content provided"},
            )

        prompt = _build_review_prompt(ctx)
        tokens_used = 0
        ai_provider = None
        ai_model = None
        analysis_summary = "LLM business-logic analysis completed."

        try:
            req = model_router.ModelRequest(
                system_prompt=BUSINESS_LOGIC_SYSTEM,
                prompt=prompt,
                temperature=0.05,
                max_tokens=4096,
            )
            response_dict = await model_router.complete_json(
                req,
                preferred_provider=ctx.ai_provider,
                preferred_model=ctx.ai_model,
            )

            raw_findings = response_dict.get("findings", [])
            tokens_used = response_dict.get("_tokens", 0)
            ai_provider = response_dict.get("_provider")
            ai_model = response_dict.get("_model")
            analysis_summary = response_dict.get("analysis_summary", analysis_summary)

        except model_router.ModelUnavailableError as exc:
            log.warning(
                "Business logic agent: LLM unavailable",
                scan_id=ctx.scan_id,
                error=str(exc),
            )
            return AgentResult(
                agent_name=self.name,
                success=True,  # Not a failure — just no LLM available
                findings=[],
                extra={"llm_unavailable": True, "reason": str(exc)},
            )

        except ValueError as exc:
            log.error("Business logic agent: invalid LLM response", scan_id=ctx.scan_id, error=str(exc))
            return AgentResult(
                agent_name=self.name,
                success=False,
                error="LLM returned invalid JSON for business logic analysis.",
                error_detail=str(exc),
            )

        # Normalize and enrich findings
        enriched: list[dict] = []
        for f in raw_findings:
            if not f.get("title") or not f.get("description"):
                continue  # Skip malformed entries

            # Assign fingerprint
            fp_input = f"{f.get('rule_id', '')}:{f.get('file_path', '')}:{f.get('line_start', 0)}:{f.get('title', '')}"
            f["fingerprint"] = hashlib.sha256(fp_input.encode()).hexdigest()[:16]
            f["agent_type"] = "business_logic"
            f.setdefault("fix_available", False)
            f.setdefault("fix_complexity", "moderate")
            f.setdefault("compliance_frameworks", [])
            f.setdefault("confidence", "medium")
            f.setdefault("source", "llm_business_logic")
            enriched.append(f)

        log.info(
            "Business logic review complete",
            scan_id=ctx.scan_id,
            findings=len(enriched),
        )

        return AgentResult(
            agent_name=self.name,
            success=True,
            findings=enriched,
            tokens_used=tokens_used,
            ai_provider=ai_provider,
            ai_model=ai_model,
            extra={
                "analysis_summary": analysis_summary,
                "llm_enabled": True,
                "llm_provider": ai_provider,
                "llm_model": ai_model,
            },
        )
