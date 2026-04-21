"""
CodeSentinel — Application Configuration
Pydantic v2 settings with full environment variable validation.
"""
from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Any, List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────
    APP_NAME: str = "CodeSentinel"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "fallback-insecure-secret-key-change-me-in-production"
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    CORS_ALLOW_ORIGIN_REGEX: Optional[str] = r"^https://[a-z0-9-]+\.vercel\.app$"

    # ── Database ───────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://codesentinel:password@localhost:5432/codesentinel"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_ECHO: bool = False

    # ── Redis + Celery ─────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    SCAN_WORKER_SLOTS: int = 1

    # ── JWT ────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "fallback-insecure-jwt-key-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Encryption ─────────────────────────────────────────────────
    ENCRYPTION_KEY: Optional[str] = None

    # ── GitHub App ─────────────────────────────────────────────────
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_APP_NAME: str = "codesentinel"
    GITHUB_APP_PRIVATE_KEY: Optional[str] = None
    GITHUB_APP_WEBHOOK_SECRET: Optional[str] = None
    GITHUB_WEBHOOK_URL: Optional[str] = None
    GITHUB_APP_CLIENT_ID: Optional[str] = None
    GITHUB_APP_CLIENT_SECRET: Optional[str] = None

    # ── GitLab ─────────────────────────────────────────────────────
    GITLAB_APP_ID: Optional[str] = None
    GITLAB_APP_SECRET: Optional[str] = None
    GITLAB_WEBHOOK_SECRET: Optional[str] = None

    # ── Bitbucket ──────────────────────────────────────────────────
    BITBUCKET_APP_KEY: Optional[str] = None
    BITBUCKET_APP_SECRET: Optional[str] = None
    BITBUCKET_WEBHOOK_SECRET: Optional[str] = None

    # ── AI: Ollama ─────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "codellama:13b"
    OLLAMA_TIMEOUT: int = 120

    # ── AI: Groq ───────────────────────────────────────────────────
    GROQ_API_KEY: Optional[str] = None
    GROQ_DEFAULT_MODEL: str = "llama-3.1-70b-versatile"

    # ── AI: Optional paid ──────────────────────────────────────────
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_DEFAULT_MODEL: str = "claude-3-5-sonnet-20241022"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_DEFAULT_MODEL: str = "gemini-1.5-flash"
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_DEFAULT_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"

    # ── Platform Provider Keys (shared defaults) ──────────────────
    PLATFORM_GEMINI_API_KEY: Optional[str] = None
    PLATFORM_OPENROUTER_API_KEY: Optional[str] = None
    PLATFORM_GROQ_API_KEY: Optional[str] = None

    # ── Notifications ──────────────────────────────────────────────
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_DEFAULT_CHANNEL: str = "#security-alerts"
    TEAMS_WEBHOOK_URL: Optional[str] = None
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "noreply@codesentinel.dev"

    # ── Issue Trackers ─────────────────────────────────────────────
    JIRA_BASE_URL: Optional[str] = None
    JIRA_API_TOKEN: Optional[str] = None
    JIRA_USER_EMAIL: Optional[str] = None
    JIRA_PROJECT_KEY: str = "SEC"
    LINEAR_API_KEY: Optional[str] = None
    LINEAR_TEAM_ID: Optional[str] = None

    # ── Rate Limiting ──────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    SCAN_RATE_LIMIT_PER_HOUR: int = 100

    # ── Computed ───────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def github_app_pem(self) -> Optional[str]:
        if not self.GITHUB_APP_PRIVATE_KEY:
            return None
        key = self.GITHUB_APP_PRIVATE_KEY.strip()

        # Railway/Render env values are often wrapped in JSON or shell quotes.
        if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
            key = key[1:-1]

        # Attempt JSON unescape first when value is provided as a JSON string.
        if "\\n" in key:
            try:
                key = key.encode("utf-8").decode("unicode_escape")
            except Exception:
                key = key.replace("\\n", "\n")

        key = key.replace("\r\n", "\n").replace("\r", "\n").strip()

        # If the key doesn't have PEM headers, add them.
        if "-----BEGIN" not in key or "-----END" not in key:
            raw = key.replace("\n", "").replace(" ", "")
            lines = [raw[i:i + 64] for i in range(0, len(raw), 64)]
            key = "-----BEGIN RSA PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END RSA PRIVATE KEY-----"

        if not key.endswith("\n"):
            key += "\n"

        return key

    @property
    def github_configured(self) -> bool:
        return bool(self.GITHUB_APP_ID and self.GITHUB_APP_PRIVATE_KEY and self.GITHUB_APP_WEBHOOK_SECRET)

    @property
    def available_ai_providers(self) -> List[str]:
        providers = ["ollama"]
        if self.GROQ_API_KEY:
            providers.append("groq")
        if self.OPENAI_API_KEY:
            providers.append("openai")
        if self.ANTHROPIC_API_KEY:
            providers.append("anthropic")
        if self.GEMINI_API_KEY:
            providers.append("gemini")
        if self.OPENROUTER_API_KEY:
            providers.append("openrouter")
        return providers

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            import json
            # Handle JSON array strings like '["https://example.com","http://localhost"]'
            stripped = v.strip()
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [o.strip() for o in parsed if isinstance(o, str) and o.strip()]
                except (json.JSONDecodeError, ValueError):
                    pass
            # Fallback: comma-separated string
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def auto_encryption_key(self) -> "Settings":
        # Always include FRONTEND_URL in allowed origins for browser auth flows.
        if self.FRONTEND_URL and self.FRONTEND_URL not in self.ALLOWED_ORIGINS:
            self.ALLOWED_ORIGINS.append(self.FRONTEND_URL)

        if not self.ENCRYPTION_KEY and not self.is_production:
            from cryptography.fernet import Fernet
            self.ENCRYPTION_KEY = Fernet.generate_key().decode()
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
