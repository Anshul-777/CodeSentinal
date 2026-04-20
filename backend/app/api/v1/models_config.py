"""
CodeSentinel — AI Models Configuration API
Let users view/switch AI providers, check availability, test connections.
"""
from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.organization import Organization
from app.models.user import User

router = APIRouter()
log = structlog.get_logger("api.models")


class ModelPreferenceRequest(BaseModel):
    provider: str
    model: Optional[str] = None


class TestPromptRequest(BaseModel):
    provider: str
    model: Optional[str] = None
    prompt: str = "Say 'CodeSentinel AI test successful' and nothing else."


@router.get("/models/providers")
async def list_providers(current_user: User = Depends(get_current_user)):
    """Return all configured AI providers with their availability status."""
    from app.ai.model_router import get_provider_statuses, AIProvider
    from app.core.config import settings

    statuses = await get_provider_statuses()

    providers = []
    for ps in statuses:
        meta = _provider_meta(ps.provider)
        providers.append({
            "id": ps.provider,
            "name": meta["name"],
            "description": meta["description"],
            "type": meta["type"],
            "cost": meta["cost"],
            "model": ps.model,
            "available": ps.available,
            "error": ps.error,
            "latency_ms": ps.latency_ms,
            "configured": _is_configured(ps.provider),
            "setup_url": meta["setup_url"],
        })

    return {"providers": providers}


@router.post("/models/test")
async def test_provider(
    payload: TestPromptRequest,
    current_user: User = Depends(get_current_user),
):
    """Test a specific provider with a simple prompt. Returns real response or error."""
    from app.ai.model_router import complete, ModelRequest, ModelUnavailableError, QuotaExhaustedError

    req = ModelRequest(
        prompt=payload.prompt,
        system_prompt="You are a test assistant. Respond with exactly what is asked.",
        temperature=0.0,
        max_tokens=50,
        provider_override=payload.provider,
        model_override=payload.model,
    )

    try:
        response = await complete(req, preferred_provider=payload.provider, preferred_model=payload.model)
        return {
            "success": True,
            "content": response.content,
            "provider": response.provider,
            "model": response.model,
            "latency_ms": round(response.latency_ms, 1),
            "tokens": response.total_tokens,
        }
    except QuotaExhaustedError as exc:
        return {"success": False, "error": "quota_exhausted", "message": str(exc), "provider": payload.provider}
    except ModelUnavailableError as exc:
        return {"success": False, "error": "unavailable", "message": str(exc), "provider": payload.provider}
    except Exception as exc:
        return {"success": False, "error": "unknown", "message": str(exc), "provider": payload.provider}


@router.patch("/models/preference")
async def set_model_preference(
    payload: ModelPreferenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set the organization's preferred AI provider and model."""
    if not current_user.primary_org_id:
        raise HTTPException(status_code=400, detail="No organization.")

    result = await db.execute(select(Organization).where(Organization.id == current_user.primary_org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    org.ai_provider_preference = payload.provider
    org.ai_model_preference = payload.model
    await db.commit()

    return {"provider": payload.provider, "model": payload.model, "message": "Preference saved."}


def _provider_meta(provider: str) -> dict:
    meta = {
        "ollama": {
            "name": "Ollama (Local)",
            "description": "Run open-source models locally — 100% free, no data leaves your machine.",
            "type": "local",
            "cost": "Free",
            "setup_url": "https://ollama.com/download",
        },
        "groq": {
            "name": "Groq",
            "description": "Free-tier inference for Llama 3.1, Mixtral, and Gemma models. Fast.",
            "type": "cloud_free",
            "cost": "Free tier available",
            "setup_url": "https://console.groq.com",
        },
        "openai": {
            "name": "OpenAI",
            "description": "GPT-4o and GPT-4o-mini. Best accuracy for complex code analysis.",
            "type": "cloud_paid",
            "cost": "Pay per token",
            "setup_url": "https://platform.openai.com/api-keys",
        },
        "anthropic": {
            "name": "Anthropic Claude",
            "description": "Claude 3.5 Sonnet — excellent code understanding and security reasoning.",
            "type": "cloud_paid",
            "cost": "Pay per token",
            "setup_url": "https://console.anthropic.com",
        },
        "gemini": {
            "name": "Google Gemini",
            "description": "Gemini 1.5 Pro/Flash — large context window, good for full-repo analysis.",
            "type": "cloud_paid",
            "cost": "Pay per token",
            "setup_url": "https://aistudio.google.com/app/apikey",
        },
        "openrouter": {
            "name": "OpenRouter",
            "description": "Access 100+ models with one API key. Useful for model comparison.",
            "type": "cloud_paid",
            "cost": "Pay per token",
            "setup_url": "https://openrouter.ai/keys",
        },
    }
    return meta.get(provider, {"name": provider, "description": "", "type": "unknown", "cost": "Unknown", "setup_url": ""})


def _is_configured(provider: str) -> bool:
    from app.core.config import settings
    mapping = {
        "ollama": True,  # Always potentially available (local)
        "groq": bool(settings.GROQ_API_KEY),
        "openai": bool(settings.OPENAI_API_KEY),
        "anthropic": bool(settings.ANTHROPIC_API_KEY),
        "gemini": bool(settings.GEMINI_API_KEY),
        "openrouter": bool(settings.OPENROUTER_API_KEY),
    }
    return mapping.get(provider, False)
