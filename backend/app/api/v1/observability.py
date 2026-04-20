"""
CodeSentinel — Observability API
System health, Celery queue depth, scan throughput, provider availability.
"""
from __future__ import annotations

import asyncio
import time

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import check_db_connection, get_db
from app.core.security import get_current_user
from app.models.scan import Scan
from app.models.user import User

router = APIRouter()
log = structlog.get_logger("api.observability")


@router.get("/observability/health")
async def system_health(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full system health check for the observability dashboard."""
    checks = {}
    start = time.perf_counter()

    # Database
    db_ok = await check_db_connection()
    checks["database"] = {"status": "healthy" if db_ok else "unhealthy", "latency_ms": round((time.perf_counter() - start) * 1000, 1)}

    # Redis
    redis_ok = False
    redis_latency = 0.0
    try:
        import redis.asyncio as aioredis
        t0 = time.perf_counter()
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        redis_ok = True
        redis_latency = round((time.perf_counter() - t0) * 1000, 1)
    except Exception:
        pass
    checks["redis"] = {"status": "healthy" if redis_ok else "unhealthy", "latency_ms": redis_latency}

    # AI providers
    from app.ai.model_router import get_provider_statuses
    provider_statuses = await get_provider_statuses()
    checks["ai_providers"] = [
        {
            "provider": p.provider,
            "model": p.model,
            "available": p.available,
            "error": p.error,
            "latency_ms": p.latency_ms,
        }
        for p in provider_statuses
    ]

    # Scan queue depth
    queued_result = await db.execute(
        select(func.count()).select_from(Scan).where(Scan.status == "queued")
    )
    running_result = await db.execute(
        select(func.count()).select_from(Scan).where(Scan.status == "running")
    )
    checks["scan_queue"] = {
        "queued": queued_result.scalar() or 0,
        "running": running_result.scalar() or 0,
    }

    overall = "healthy" if (db_ok and redis_ok) else ("degraded" if db_ok else "unhealthy")
    return {
        "overall": overall,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "checks": checks,
        "github_configured": settings.github_configured,
        "ai_providers_configured": settings.available_ai_providers,
    }


@router.get("/observability/metrics")
async def scan_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Scan throughput and performance metrics for the observability dashboard."""
    from datetime import datetime, timezone, timedelta
    from app.models.repository import Repository
    from sqlalchemy import and_

    if not current_user.primary_org_id:
        return {}

    repo_ids_r = await db.execute(
        select(Repository.id).where(Repository.organization_id == current_user.primary_org_id)
    )
    repo_ids = [str(r[0]) for r in repo_ids_r.fetchall()]
    if not repo_ids:
        return {"total_scans": 0}

    now = datetime.now(timezone.utc)
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)

    # Total scans
    total_r = await db.execute(select(func.count()).select_from(Scan).where(Scan.repository_id.in_(repo_ids)))
    total_scans = total_r.scalar() or 0

    # Last 7 days
    week_r = await db.execute(
        select(func.count()).select_from(Scan).where(Scan.repository_id.in_(repo_ids), Scan.created_at >= last_7_days)
    )
    scans_last_7d = week_r.scalar() or 0

    # Average duration
    avg_dur_r = await db.execute(
        select(func.avg(Scan.duration_seconds)).where(
            Scan.repository_id.in_(repo_ids),
            Scan.status == "completed",
            Scan.duration_seconds.isnot(None),
        )
    )
    avg_duration = round(avg_dur_r.scalar() or 0, 1)

    # Scans per day last 7 days
    from sqlalchemy import cast, Date
    daily_r = await db.execute(
        select(
            func.date(Scan.created_at).label("day"),
            func.count(Scan.id).label("count"),
        )
        .where(Scan.repository_id.in_(repo_ids), Scan.created_at >= last_7_days)
        .group_by(func.date(Scan.created_at))
        .order_by(func.date(Scan.created_at))
    )
    daily_scans = [{"date": str(row[0]), "count": row[1]} for row in daily_r.fetchall()]

    # Status breakdown
    status_r = await db.execute(
        select(Scan.status, func.count(Scan.id))
        .where(Scan.repository_id.in_(repo_ids))
        .group_by(Scan.status)
    )
    status_breakdown = {row[0]: row[1] for row in status_r.fetchall()}

    return {
        "total_scans": total_scans,
        "scans_last_7_days": scans_last_7d,
        "avg_scan_duration_seconds": avg_duration,
        "daily_scans": daily_scans,
        "status_breakdown": status_breakdown,
    }
