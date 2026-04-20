"""
CodeSentinel — AI Models Configuration API
Let users view/switch AI providers, check availability, test connections.
"""
from __future__ import annotations

import os
from pathlib import Path
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

PROVIDER_MODELS: dict[str, list[str]] = {
    "ollama": [
        "codellama:13b",
        "llama3.1:8b",
        "qwen2.5-coder:7b",
    ],
    "groq": [
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
        "gemma2-9b-it",
    ],
    "gemini": [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
    ],
    "openrouter": [
        "meta-llama/llama-3.1-8b-instruct:free",
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
    ],
    "anthropic": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
    ],
}


class ModelPreferenceRequest(BaseModel):
    provider: str
    model: Optional[str] = None


class TestPromptRequest(BaseModel):
    provider: str
    model: Optional[str] = None
    prompt: str = "Hello, The Model is active"


class ConfigureProviderRequest(BaseModel):
    provider: str
    api_key: str


@router.get("/models/providers")
async def list_providers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all configured AI providers with their availability status."""
    from app.ai.model_router import get_provider_statuses, AIProvider
    from app.core.config import settings

    statuses = await get_provider_statuses()

    preferred_provider = None
    preferred_model = None
    if current_user.primary_org_id:
        result = await db.execute(select(Organization).where(Organization.id == current_user.primary_org_id))
        org = result.scalar_one_or_none()
        if org:
            preferred_provider = org.ai_provider_preference
            preferred_model = org.ai_model_preference

    providers = []
    priority_order = ["gemini", "openrouter", "groq", "ollama", "openai", "anthropic"]
    personal_candidates: list[dict] = []
    provider_candidates: list[dict] = []

    for ps in statuses:
        meta = _provider_meta(ps.provider)
        models = PROVIDER_MODELS.get(ps.provider, [ps.model])
        effective_model = preferred_model if preferred_provider == ps.provider and preferred_model else ps.model
        provider_data = {
            "id": ps.provider,
            "name": meta["name"],
            "description": meta["description"],
            "type": meta["type"],
            "cost": meta["cost"],
            "model": effective_model,
            "default_model": ps.model,
            "models": models,
            "available": ps.available,
            "error": ps.error,
            "latency_ms": ps.latency_ms,
            "configured": _is_configured(ps.provider),
            "source": ps.source,
            "setup_url": meta["setup_url"],
            "selected": preferred_provider == ps.provider,
        }
        providers.append(provider_data)

        if ps.source == "personal":
            personal_candidates.append(provider_data)
        else:
            provider_candidates.append(provider_data)

    def rank(provider_id: str) -> int:
        return priority_order.index(provider_id) if provider_id in priority_order else 999

    personal_candidates.sort(key=lambda p: rank(p["id"]))

    for idx, item in enumerate(personal_candidates):
        item["category"] = "personal_models"
        item["priority_tag"] = "primary" if idx == 0 else "secondary"

    for item in provider_candidates:
        item["category"] = "provider_models"
        item["priority_tag"] = "provider"

    providers.sort(key=lambda p: rank(p["id"]))

    return {
        "providers": providers,
        "provider_models": sorted(provider_candidates, key=lambda p: rank(p["id"])),
        "personal_models": personal_candidates,
        "active_mode": "personal" if personal_candidates else "provider",
    }


@router.post("/models/test")
async def test_provider(
    payload: TestPromptRequest,
    current_user: User = Depends(get_current_user),
):
    """Test a specific provider with a simple prompt. Returns real response or error."""
    from app.ai.model_router import complete, ModelRequest, ModelUnavailableError, QuotaExhaustedError

    req = ModelRequest(
        prompt=payload.prompt,
        system_prompt="You are a test assistant. Respond with exactly the requested sentence and no extra words.",
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


@router.post("/models/configure")
async def configure_provider_key(
    payload: ConfigureProviderRequest,
    current_user: User = Depends(get_current_user),
):
    """Store/clear provider API key in env and apply it immediately for this process."""
    provider_env_map = {
        "groq": "GROQ_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }

    provider = payload.provider.strip().lower()
    env_key = provider_env_map.get(provider)
    if not env_key:
        raise HTTPException(status_code=400, detail="Provider does not require API key configuration.")

    raw_value = (payload.api_key or "").strip()
    cleared = raw_value == "" or raw_value.upper() == "NONE"
    value = "" if cleared else raw_value

    # Persist in backend/.env (mounted to /app/.env in docker and used locally in backend/).
    _upsert_env_var(Path(".env"), env_key, value)

    # Apply immediately in-process so no restart is required.
    if value:
        os.environ[env_key] = value
    else:
        os.environ.pop(env_key, None)
    from app.core.config import settings
    setattr(settings, env_key, value or None)

    return {
        "provider": provider,
        "configured": bool(value),
        "message": "API key saved." if value else "API key cleared.",
    }


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
            "description": "Gemini Flash/Pro models with optional free quota depending on Google account limits.",
            "type": "cloud_free",
            "cost": "Free tier / Pay as you go",
            "setup_url": "https://aistudio.google.com/app/apikey",
        },
        "openrouter": {
            "name": "OpenRouter",
            "description": "Access multiple models including free-tier options with one API key.",
            "type": "cloud_free",
            "cost": "Free + Pay as you go",
            "setup_url": "https://openrouter.ai/keys",
        },
    }
    return meta.get(provider, {"name": provider, "description": "", "type": "unknown", "cost": "Unknown", "setup_url": ""})


def _is_configured(provider: str) -> bool:
    from app.core.config import settings
    mapping = {
        "ollama": True,  # Always potentially available (local)
        "groq": bool(settings.GROQ_API_KEY or settings.PLATFORM_GROQ_API_KEY),
        "openai": bool(settings.OPENAI_API_KEY),
        "anthropic": bool(settings.ANTHROPIC_API_KEY),
        "gemini": bool(settings.GEMINI_API_KEY or settings.PLATFORM_GEMINI_API_KEY),
        "openrouter": bool(settings.OPENROUTER_API_KEY or settings.PLATFORM_OPENROUTER_API_KEY),
    }
    return mapping.get(provider, False)


def _upsert_env_var(env_path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    replaced = False
    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{key}={value}"
            replaced = True
            break

    if not replaced:
        lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
