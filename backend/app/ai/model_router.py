"""
CodeSentinel — AI Model Router
Routes LLM calls to the right provider: Ollama → Groq → OpenAI → Anthropic → OpenRouter.
Supports per-agent model overrides, honest quota/availability states, and fallback chain.
Never fakes responses. If all providers fail, raises ModelUnavailableError.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Optional

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger("ai.router")


class AIProvider(str, Enum):
    OLLAMA = "ollama"
    GROQ = "groq"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


class ModelUnavailableError(Exception):
    """Raised when no AI provider is available or all have failed."""
    def __init__(self, message: str, provider: Optional[str] = None, details: Optional[str] = None):
        super().__init__(message)
        self.provider = provider
        self.details = details


class QuotaExhaustedError(ModelUnavailableError):
    """Raised when a provider key exists but quota is exhausted."""
    pass


@dataclass
class ModelRequest:
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4096
    # Agent-specific model override — None means use org default
    provider_override: Optional[str] = None
    model_override: Optional[str] = None


@dataclass
class ModelResponse:
    content: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    raw: Optional[dict] = None


@dataclass
class ProviderStatus:
    provider: str
    model: str
    available: bool
    source: str = "none"
    error: Optional[str] = None
    latency_ms: Optional[float] = None


def _has_personal_cloud_key() -> bool:
    return any([
        bool(settings.GEMINI_API_KEY),
        bool(settings.OPENROUTER_API_KEY),
        bool(settings.GROQ_API_KEY),
        bool(settings.OPENAI_API_KEY),
        bool(settings.ANTHROPIC_API_KEY),
    ])


def _resolve_api_key(provider: AIProvider) -> tuple[Optional[str], str]:
    personal = {
        AIProvider.GROQ: settings.GROQ_API_KEY,
        AIProvider.OPENAI: settings.OPENAI_API_KEY,
        AIProvider.ANTHROPIC: settings.ANTHROPIC_API_KEY,
        AIProvider.GEMINI: settings.GEMINI_API_KEY,
        AIProvider.OPENROUTER: settings.OPENROUTER_API_KEY,
    }
    platform = {
        AIProvider.GROQ: settings.PLATFORM_GROQ_API_KEY,
        AIProvider.OPENAI: None,
        AIProvider.ANTHROPIC: None,
        AIProvider.GEMINI: settings.PLATFORM_GEMINI_API_KEY,
        AIProvider.OPENROUTER: settings.PLATFORM_OPENROUTER_API_KEY,
    }

    personal_key = personal.get(provider)
    if personal_key:
        return personal_key, "personal"

    platform_key = platform.get(provider)
    if platform_key:
        return platform_key, "provider"

    return None, "none"


class OllamaAdapter:
    """Local Ollama adapter — truly free, no registration needed."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.timeout = settings.OLLAMA_TIMEOUT

    @property
    def default_model(self) -> str:
        return settings.OLLAMA_DEFAULT_MODEL

    async def is_available(self) -> tuple[bool, Optional[str]]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    if not models:
                        return False, "Ollama is running but no models are pulled. Run: ollama pull codellama:13b"
                    return True, None
                return False, f"Ollama returned status {resp.status_code}"
        except Exception as exc:
            return False, f"Ollama not reachable at {self.base_url}: {exc}"

    async def complete(self, req: ModelRequest, model: Optional[str] = None) -> ModelResponse:
        target_model = model or self.default_model
        start = time.perf_counter()

        messages = []
        if req.system_prompt:
            messages.append({"role": "system", "content": req.system_prompt})
        messages.append({"role": "user", "content": req.prompt})

        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": req.temperature,
                "num_predict": req.max_tokens,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            if "model not found" in str(exc).lower():
                raise ModelUnavailableError(
                    f"Model '{target_model}' not pulled in Ollama. Run: ollama pull {target_model}",
                    provider="ollama",
                    details=str(exc),
                )
            raise ModelUnavailableError(f"Ollama HTTP error: {exc}", provider="ollama", details=str(exc))
        except Exception as exc:
            raise ModelUnavailableError(f"Ollama unreachable: {exc}", provider="ollama", details=str(exc))

        latency = (time.perf_counter() - start) * 1000
        content = data.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return ModelResponse(
            content=content,
            provider="ollama",
            model=target_model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency,
            raw=data,
        )


class GroqAdapter:
    """Groq free-tier adapter — fast inference on Llama/Mixtral models."""

    def __init__(self):
        pass

    @property
    def default_model(self) -> str:
        return settings.GROQ_DEFAULT_MODEL

    def _get_api_key(self) -> tuple[Optional[str], str]:
        return _resolve_api_key(AIProvider.GROQ)

    async def is_available(self) -> tuple[bool, Optional[str]]:
        api_key, _ = self._get_api_key()
        if not api_key:
            return False, "GROQ_API_KEY not set. Register free at https://console.groq.com"
        return True, None

    async def complete(self, req: ModelRequest, model: Optional[str] = None) -> ModelResponse:
        api_key, _ = self._get_api_key()
        if not api_key:
            raise ModelUnavailableError("GROQ_API_KEY not configured.", provider="groq")

        target_model = model or self.default_model
        start = time.perf_counter()

        messages = []
        if req.system_prompt:
            messages.append({"role": "system", "content": req.system_prompt})
        messages.append({"role": "user", "content": req.prompt})

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": target_model,
                        "messages": messages,
                        "temperature": req.temperature,
                        "max_tokens": req.max_tokens,
                    },
                )
                if resp.status_code == 429:
                    raise QuotaExhaustedError("Groq rate limit or quota exhausted.", provider="groq", details=resp.text)
                resp.raise_for_status()
                data = resp.json()
        except QuotaExhaustedError:
            raise
        except Exception as exc:
            raise ModelUnavailableError(f"Groq API error: {exc}", provider="groq", details=str(exc))

        latency = (time.perf_counter() - start) * 1000
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return ModelResponse(
            content=content,
            provider="groq",
            model=target_model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency,
            raw=data,
        )


class OpenAIAdapter:
    def __init__(self):
        pass

    @property
    def default_model(self) -> str:
        return settings.OPENAI_DEFAULT_MODEL

    def _get_api_key(self) -> tuple[Optional[str], str]:
        return _resolve_api_key(AIProvider.OPENAI)

    async def is_available(self) -> tuple[bool, Optional[str]]:
        api_key, _ = self._get_api_key()
        if not api_key:
            return False, "OPENAI_API_KEY not set."
        return True, None

    async def complete(self, req: ModelRequest, model: Optional[str] = None) -> ModelResponse:
        api_key, _ = self._get_api_key()
        if not api_key:
            raise ModelUnavailableError("OPENAI_API_KEY not configured.", provider="openai")

        target_model = model or self.default_model
        start = time.perf_counter()
        messages = []
        if req.system_prompt:
            messages.append({"role": "system", "content": req.system_prompt})
        messages.append({"role": "user", "content": req.prompt})

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": target_model, "messages": messages, "temperature": req.temperature, "max_tokens": req.max_tokens},
                )
                if resp.status_code == 429:
                    raise QuotaExhaustedError("OpenAI quota exhausted.", provider="openai")
                resp.raise_for_status()
                data = resp.json()
        except QuotaExhaustedError:
            raise
        except Exception as exc:
            raise ModelUnavailableError(f"OpenAI error: {exc}", provider="openai")

        latency = (time.perf_counter() - start) * 1000
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return ModelResponse(
            content=content, provider="openai", model=target_model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency, raw=data,
        )


class AnthropicAdapter:
    def __init__(self):
        pass

    @property
    def default_model(self) -> str:
        return settings.ANTHROPIC_DEFAULT_MODEL

    def _get_api_key(self) -> tuple[Optional[str], str]:
        return _resolve_api_key(AIProvider.ANTHROPIC)

    async def is_available(self) -> tuple[bool, Optional[str]]:
        api_key, _ = self._get_api_key()
        if not api_key:
            return False, "ANTHROPIC_API_KEY not set."
        return True, None

    async def complete(self, req: ModelRequest, model: Optional[str] = None) -> ModelResponse:
        api_key, _ = self._get_api_key()
        if not api_key:
            raise ModelUnavailableError("ANTHROPIC_API_KEY not configured.", provider="anthropic")

        target_model = model or self.default_model
        start = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                body: dict[str, Any] = {
                    "model": target_model,
                    "max_tokens": req.max_tokens,
                    "messages": [{"role": "user", "content": req.prompt}],
                }
                if req.system_prompt:
                    body["system"] = req.system_prompt

                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                if resp.status_code == 529:
                    raise QuotaExhaustedError("Anthropic overloaded.", provider="anthropic")
                resp.raise_for_status()
                data = resp.json()
        except QuotaExhaustedError:
            raise
        except Exception as exc:
            raise ModelUnavailableError(f"Anthropic error: {exc}", provider="anthropic")

        latency = (time.perf_counter() - start) * 1000
        content = data["content"][0]["text"]
        usage = data.get("usage", {})
        return ModelResponse(
            content=content, provider="anthropic", model=target_model,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            latency_ms=latency, raw=data,
        )


class GeminiAdapter:
    """Google Gemini adapter via Generative Language REST API."""

    def __init__(self):
        pass

    @property
    def default_model(self) -> str:
        return settings.GEMINI_DEFAULT_MODEL

    def _get_api_key(self) -> tuple[Optional[str], str]:
        return _resolve_api_key(AIProvider.GEMINI)

    async def is_available(self) -> tuple[bool, Optional[str]]:
        api_key, _ = self._get_api_key()
        if not api_key:
            return False, "GEMINI_API_KEY not set."
        return True, None

    async def complete(self, req: ModelRequest, model: Optional[str] = None) -> ModelResponse:
        api_key, _ = self._get_api_key()
        if not api_key:
            raise ModelUnavailableError("GEMINI_API_KEY not configured.", provider="gemini")

        target_model = model or self.default_model
        start = time.perf_counter()

        text_parts = []
        if req.system_prompt:
            text_parts.append(f"System: {req.system_prompt}")
        text_parts.append(req.prompt)
        prompt_text = "\n\n".join(text_parts)

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent"
            f"?key={api_key}"
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt_text}]}],
                        "generationConfig": {
                            "temperature": req.temperature,
                            "maxOutputTokens": req.max_tokens,
                        },
                    },
                )
                if resp.status_code == 429:
                    raise QuotaExhaustedError("Gemini quota exhausted.", provider="gemini", details=resp.text)
                resp.raise_for_status()
                data = resp.json()
        except QuotaExhaustedError:
            raise
        except Exception as exc:
            raise ModelUnavailableError(f"Gemini error: {exc}", provider="gemini", details=str(exc))

        latency = (time.perf_counter() - start) * 1000
        candidates = data.get("candidates") or []
        if not candidates:
            raise ModelUnavailableError("Gemini returned no candidates.", provider="gemini", details=str(data))
        parts = candidates[0].get("content", {}).get("parts", [])
        content = "".join(p.get("text", "") for p in parts)

        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", prompt_tokens + completion_tokens)

        return ModelResponse(
            content=content,
            provider="gemini",
            model=target_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency,
            raw=data,
        )


class OpenRouterAdapter:
    """OpenRouter adapter via OpenAI-compatible chat endpoint."""

    def __init__(self):
        pass

    @property
    def default_model(self) -> str:
        return settings.OPENROUTER_DEFAULT_MODEL

    def _get_api_key(self) -> tuple[Optional[str], str]:
        return _resolve_api_key(AIProvider.OPENROUTER)

    async def is_available(self) -> tuple[bool, Optional[str]]:
        api_key, _ = self._get_api_key()
        if not api_key:
            return False, "OPENROUTER_API_KEY not set."
        return True, None

    async def complete(self, req: ModelRequest, model: Optional[str] = None) -> ModelResponse:
        api_key, _ = self._get_api_key()
        if not api_key:
            raise ModelUnavailableError("OPENROUTER_API_KEY not configured.", provider="openrouter")

        target_model = model or self.default_model
        start = time.perf_counter()

        messages = []
        if req.system_prompt:
            messages.append({"role": "system", "content": req.system_prompt})
        messages.append({"role": "user", "content": req.prompt})

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://codesentinel.dev",
                        "X-Title": "CodeSentinel",
                    },
                    json={
                        "model": target_model,
                        "messages": messages,
                        "temperature": req.temperature,
                        "max_tokens": req.max_tokens,
                    },
                )
                if resp.status_code == 429:
                    raise QuotaExhaustedError("OpenRouter quota exhausted.", provider="openrouter", details=resp.text)
                resp.raise_for_status()
                data = resp.json()
        except QuotaExhaustedError:
            raise
        except Exception as exc:
            raise ModelUnavailableError(f"OpenRouter error: {exc}", provider="openrouter", details=str(exc))

        latency = (time.perf_counter() - start) * 1000
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return ModelResponse(
            content=content,
            provider="openrouter",
            model=target_model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency,
            raw=data,
        )


# ── Singleton adapters ────────────────────────────────────────────────────────
_ollama = OllamaAdapter()
_groq = GroqAdapter()
_openai = OpenAIAdapter()
_anthropic = AnthropicAdapter()
_gemini = GeminiAdapter()
_openrouter = OpenRouterAdapter()

_ADAPTERS = {
    AIProvider.OLLAMA: _ollama,
    AIProvider.GROQ: _groq,
    AIProvider.OPENAI: _openai,
    AIProvider.ANTHROPIC: _anthropic,
    AIProvider.GEMINI: _gemini,
    AIProvider.OPENROUTER: _openrouter,
}

# Fallback chain: local first, then free cloud, then paid
_FALLBACK_ORDER = [
    AIProvider.GEMINI,
    AIProvider.OPENROUTER,
    AIProvider.GROQ,
    AIProvider.OLLAMA,
    AIProvider.OPENAI,
    AIProvider.ANTHROPIC,
]


async def get_provider_statuses() -> list[ProviderStatus]:
    """Return availability status for all configured providers (for the UI model settings page)."""
    statuses = []
    for provider, adapter in _ADAPTERS.items():
        t0 = time.perf_counter()
        available, error = await adapter.is_available()
        latency = (time.perf_counter() - t0) * 1000
        model = getattr(adapter, "default_model", "unknown")
        source = "provider"
        if provider in {AIProvider.GROQ, AIProvider.OPENAI, AIProvider.ANTHROPIC, AIProvider.GEMINI, AIProvider.OPENROUTER}:
            _, source = _resolve_api_key(provider)
        statuses.append(ProviderStatus(
            provider=provider.value,
            model=model,
            available=available,
            source=source,
            error=error,
            latency_ms=round(latency, 1) if available else None,
        ))
    return statuses


async def complete(
    req: ModelRequest,
    preferred_provider: Optional[str] = None,
    preferred_model: Optional[str] = None,
) -> ModelResponse:
    """
    Route a completion request through the provider hierarchy.
    Never returns a fake response. Raises ModelUnavailableError if all fail.
    """
    # Apply per-request overrides
    if req.provider_override:
        preferred_provider = req.provider_override
    if req.model_override:
        preferred_model = req.model_override

    # Build ordered list starting with preferred
    order = []
    if preferred_provider:
        try:
            order.append(AIProvider(preferred_provider))
        except ValueError:
            log.warning("Unknown preferred provider", provider=preferred_provider)

    for p in _FALLBACK_ORDER:
        if p not in order:
            order.append(p)

    last_error: Optional[Exception] = None

    personal_mode = _has_personal_cloud_key()

    for provider_enum in order:
        adapter = _ADAPTERS.get(provider_enum)
        if not adapter:
            continue

        if personal_mode and provider_enum != AIProvider.OLLAMA:
            _, source = _resolve_api_key(provider_enum)
            if source != "personal":
                log.debug("Skipping provider defaults because personal mode is active", provider=provider_enum.value)
                continue

        available, unavail_reason = await adapter.is_available()
        if not available:
            log.debug("Provider not available, skipping", provider=provider_enum.value, reason=unavail_reason)
            continue

        try:
            log.info("Calling AI provider", provider=provider_enum.value, model=preferred_model or getattr(adapter, "default_model", "?"))
            model_override = preferred_model if preferred_provider == provider_enum.value else None
            result = await adapter.complete(req, model=model_override)
            log.info(
                "AI response received",
                provider=result.provider,
                model=result.model,
                tokens=result.total_tokens,
                latency_ms=round(result.latency_ms, 1),
            )
            return result
        except QuotaExhaustedError as exc:
            log.warning("Quota exhausted, falling back", provider=provider_enum.value, detail=str(exc))
            last_error = exc
            continue
        except ModelUnavailableError as exc:
            log.warning("Provider failed, falling back", provider=provider_enum.value, detail=str(exc))
            last_error = exc
            continue
        except Exception as exc:
            log.error("Unexpected AI error", provider=provider_enum.value, error=str(exc))
            last_error = exc
            continue

    raise ModelUnavailableError(
        "All AI providers are unavailable. "
        "Please configure at least one Personal Model key, or switch to Provider Models defaults.",
        details=str(last_error) if last_error else None,
    )


async def complete_json(
    req: ModelRequest,
    preferred_provider: Optional[str] = None,
    preferred_model: Optional[str] = None,
) -> dict:
    """Complete and parse JSON response. Strips markdown fences if present."""
    response = await complete(req, preferred_provider=preferred_provider, preferred_model=preferred_model)
    text = response.content.strip()
    # Strip ```json ... ``` or ``` ... ``` fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload.setdefault("_provider", response.provider)
            payload.setdefault("_model", response.model)
            payload.setdefault("_tokens", response.total_tokens)
        return payload
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI response was not valid JSON: {exc}\nRaw content: {text[:500]}")
