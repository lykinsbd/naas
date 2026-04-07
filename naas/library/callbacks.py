"""
callbacks.py
RQ job callbacks for post-job cleanup (dedup key deletion, webhook firing, etc.)
"""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from rq import Callback, Queue, Retry

from naas.config import WEBHOOK_MAX_RETRIES
from naas.library.audit import emit_audit_event
from naas.library.dedup import clear_dedup_key
from naas.library.webhook import deliver_webhook

if TYPE_CHECKING:
    from rq.job import Job

logger = logging.getLogger(__name__)

# Exponential backoff: 5s, 30s, 5min, 30min
_RETRY_INTERVALS = [5, 30, 300, 1800]


def _get_completed_at() -> str:
    return datetime.now(tz=UTC).isoformat()


def _on_webhook_failure(job: "Job", connection, type, value, traceback) -> None:
    """Called when all webhook delivery retries are exhausted."""
    meta = job.meta if isinstance(job.meta, dict) else {}
    emit_audit_event(
        "webhook.failed",
        job_id=meta.get("source_job_id", ""),
        webhook_url=meta.get("webhook_url", ""),
        attempts=WEBHOOK_MAX_RETRIES,
        last_error=str(value),
    )


def _fire_webhook_if_configured(job: "Job", connection, status: str) -> None:
    """Enqueue webhook delivery as a retryable RQ job."""
    webhook_url = job.meta.get("webhook_url", "") if isinstance(job.meta, dict) else ""
    if not webhook_url:
        return
    webhook_secret = job.meta.get("webhook_secret", "") if isinstance(job.meta, dict) else ""
    enqueued_at = job.enqueued_at.isoformat() if job.enqueued_at else ""

    max_retries = max(WEBHOOK_MAX_RETRIES - 1, 0)
    intervals = _RETRY_INTERVALS[:max_retries]

    q = Queue("webhooks", connection=connection)
    q.enqueue(
        deliver_webhook,
        webhook_url,
        job.id,
        status,
        enqueued_at,
        _get_completed_at(),
        webhook_secret,
        retry=Retry(max=max_retries, interval=intervals),
        on_failure=Callback(_on_webhook_failure),
        meta={"source_job_id": job.id, "webhook_url": webhook_url},
    )


def on_job_complete(job: "Job", connection, result, *args, **kwargs) -> None:
    """
    Called by RQ after a job succeeds.
    Clears the dedup key and fires webhook if configured.
    """
    dedup_key = job.meta.get("dedup_key", "") if isinstance(job.meta, dict) else ""
    if dedup_key:
        clear_dedup_key(dedup_key, connection)
    _fire_webhook_if_configured(job, connection, "finished")


def on_job_failure(job: "Job", connection, type, value, traceback) -> None:
    """
    Called by RQ after a job fails.
    Clears the dedup key and fires webhook if configured.
    """
    dedup_key = job.meta.get("dedup_key", "") if isinstance(job.meta, dict) else ""
    if dedup_key:
        clear_dedup_key(dedup_key, connection)
    _fire_webhook_if_configured(job, connection, "failed")
