"""
CodeSentinel — Celery Application
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

from app.core.config import settings

celery_app = Celery(
    "codesentinel",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.scan_tasks"],
)

default_exchange = Exchange("default", type="direct")
priority_exchange = Exchange("priority", type="direct")

celery_app.conf.task_queues = (
    Queue("default", default_exchange, routing_key="default"),
    Queue("scans", default_exchange, routing_key="scans"),
    Queue("agents", default_exchange, routing_key="agents"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    task_max_retries=3,
    task_default_retry_delay=60,
    task_soft_time_limit=600,
    task_time_limit=900,
    worker_concurrency=4,
    beat_schedule={
        "cleanup-old-scan-jobs": {
            "task": "app.tasks.scan_tasks.cleanup_old_jobs",
            "schedule": crontab(hour="2", minute="0"),
        },
        "refresh-vulnerability-db": {
            "task": "app.tasks.scan_tasks.refresh_vulnerability_db",
            "schedule": crontab(hour="*/6"),
        },
    },
)
