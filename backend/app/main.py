"""
CodeSentinel — FastAPI Application
All routers registered, all middleware configured.
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.database import check_db_connection, engine
import app.core.logging  # noqa — configures structlog on import

log = structlog.get_logger("app")

REQUEST_COUNT = Counter("cs_http_requests_total", "HTTP requests", ["method", "endpoint", "status"])
REQUEST_DURATION = Histogram("cs_http_duration_seconds", "HTTP duration", ["method", "endpoint"])
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("CodeSentinel starting", env=settings.APP_ENV, version=settings.APP_VERSION)
    db_ok = await check_db_connection()
    if db_ok:
        log.info("Database connected")
    else:
        log.error("Database connection FAILED — check DATABASE_URL in .env")
    yield
    log.info("Shutting down — disposing DB connections")
    await engine.dispose()


app = FastAPI(
    title="CodeSentinel API",
    version=settings.APP_VERSION,
    description="AI-powered DevSecOps security platform — 5-agent CI/CD pipeline integration",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    request.state.request_id = request_id
    response: Response = await call_next(request)
    duration = time.perf_counter() - start
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{duration:.4f}"
    if not request.url.path.startswith(("/health", "/metrics")):
        p = request.url.path
        REQUEST_COUNT.labels(method=request.method, endpoint=p, status=response.status_code).inc()
        REQUEST_DURATION.labels(method=request.method, endpoint=p).observe(duration)
    return response


# ── API Routers ────────────────────────────────────────────────────
from app.api.v1 import (
    auth, repos, scans, findings, autofix, compliance,
    dependencies, secrets, sbom, audit, reports, policies, notifications,
    settings as settings_router, models_config, observability,
    team, integrations, webhooks,
)

API = "/api/v1"

app.include_router(auth.router, prefix=API, tags=["Authentication"])
app.include_router(repos.router, prefix=API, tags=["Repositories"])
app.include_router(scans.router, prefix=API, tags=["Scans"])
app.include_router(findings.router, prefix=API, tags=["Findings"])
app.include_router(autofix.router, prefix=API, tags=["Auto-Fix"])
app.include_router(compliance.router, prefix=API, tags=["Compliance"])
app.include_router(dependencies.router, prefix=API, tags=["Dependencies"])
app.include_router(secrets.router, prefix=API, tags=["Secrets"])
app.include_router(sbom.router, prefix=API, tags=["SBOM"])
app.include_router(audit.router, prefix=API, tags=["Audit Logs"])
app.include_router(reports.router, prefix=API, tags=["Reports"])
app.include_router(policies.router, prefix=API, tags=["Policies"])
app.include_router(notifications.router, prefix=API, tags=["Notifications"])
app.include_router(settings_router.router, prefix=API, tags=["Settings"])
app.include_router(models_config.router, prefix=API, tags=["AI Models"])
app.include_router(observability.router, prefix=API, tags=["Observability"])
app.include_router(team.router, prefix=API, tags=["Team"])
app.include_router(integrations.router, prefix=API, tags=["Integrations"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])


# ── System Endpoints ───────────────────────────────────────────────
@app.get("/health", include_in_schema=False)
async def health():
    db_ok = await check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "database": "connected" if db_ok else "disconnected",
        "github_app": settings.github_configured,
    }


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs" if settings.DEBUG else "disabled in production",
    }
