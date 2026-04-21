"""
CodeSentinel — Celery Scan Tasks
Async task workers that execute the scan pipeline in background.
"""
from __future__ import annotations

import asyncio
import structlog

from app.core.celery_app import celery_app

log = structlog.get_logger("tasks.scan")


@celery_app.task(
    name="app.tasks.scan_tasks.trigger_scan",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="scans",
)
def trigger_scan(self, scan_id: str) -> dict:
    """
    Celery task: run the full 5-agent scan pipeline for a scan ID.
    Uses asyncio.run to bridge sync Celery with async pipeline.
    """
    log.info("Scan task started", scan_id=scan_id, task_id=self.request.id)

    try:
        # Update the scan record with the Celery task ID
        from app.core.database import get_db_context
        from app.models.scan import Scan
        from sqlalchemy import select

        async def _update_task_id():
            async with get_db_context() as db:
                result = await db.execute(select(Scan).where(Scan.id == scan_id))
                scan = result.scalar_one_or_none()
                if scan:
                    scan.celery_task_id = self.request.id
                    await db.commit()

        asyncio.run(_update_task_id())

        # Run the pipeline
        from app.services.scan_service import run_scan_pipeline
        asyncio.run(run_scan_pipeline(scan_id))

        log.info("Scan task completed", scan_id=scan_id)
        return {"scan_id": scan_id, "status": "completed"}

    except Exception as exc:
        log.error("Scan task failed", scan_id=scan_id, error=str(exc), exc_info=True)

        # Update scan status to failed
        async def _mark_failed():
            from app.core.database import get_db_context
            from app.models.scan import Scan
            from sqlalchemy import select
            from datetime import datetime, timezone

            async with get_db_context() as db:
                result = await db.execute(select(Scan).where(Scan.id == scan_id))
                scan = result.scalar_one_or_none()
                if scan and scan.status not in ("completed", "blocked"):
                    scan.status = "failed"
                    scan.agent_errors = {"pipeline": str(exc)}
                    from datetime import datetime, timezone
                    scan.completed_at = datetime.now(timezone.utc)
                    await db.commit()

        asyncio.run(_mark_failed())

        raise self.retry(exc=exc) from exc


@celery_app.task(name="app.tasks.scan_tasks.cleanup_old_jobs")
def cleanup_old_jobs():
    """Remove stale queued scans older than 24 hours."""
    log.info("Running scan cleanup")
    async def _cleanup():
        from app.core.database import get_db_context
        from app.models.scan import Scan
        from sqlalchemy import select, delete
        from datetime import datetime, timezone, timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        async with get_db_context() as db:
            await db.execute(
                delete(Scan).where(
                    Scan.status == "queued",
                    Scan.created_at < cutoff,
                )
            )
            await db.commit()
    asyncio.run(_cleanup())


@celery_app.task(name="app.tasks.scan_tasks.refresh_vulnerability_db")
def refresh_vulnerability_db():
    """Placeholder for future local CVE cache refresh."""
    log.info("Vulnerability DB refresh tick (using live OSV.dev queries)")
