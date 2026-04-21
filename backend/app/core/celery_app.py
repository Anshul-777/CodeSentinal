"""
CodeSentinel — Celery Application
"""
from __future__ import annotations

from ssl import CERT_REQUIRED

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.config import settings


def _normalize_rediss_url(url: str) -> str:
    """Ensure Redis TLS URL has ssl_cert_reqs query parameter."""
    try:
        parts = urlsplit(url)
    except Exception:
        return url

    if parts.scheme != "rediss":
        return url

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "ssl_cert_reqs" not in query:
        query["ssl_cert_reqs"] = "CERT_REQUIRED"
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return url


broker_url = _normalize_rediss_url(settings.CELERY_BROKER_URL)
result_backend_url = _normalize_rediss_url(settings.CELERY_RESULT_BACKEND)

celery_app = Celery(
    "codesentinel",
    broker=broker_url,
    backend=result_backend_url,
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
    broker_use_ssl={"ssl_cert_reqs": CERT_REQUIRED} if broker_url.startswith("rediss") else None,
    redis_backend_use_ssl={"ssl_cert_reqs": CERT_REQUIRED} if result_backend_url.startswith("rediss") else None,
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
