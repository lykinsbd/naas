"""
callbacks.py
RQ job callbacks for post-job cleanup (dedup key deletion, webhook firing, etc.)
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from naas.library.dedup import clear_dedup_key
from naas.library.webhook import fire_webhook

if TYPE_CHECKING:
    from rq.job import Job


def _get_completed_at() -> str:
    return datetime.now(tz=UTC).isoformat()


def _fire_webhook_if_configured(job: "Job", status: str) -> None:
    """Fire webhook notification if webhook_url is stored in job meta."""
    webhook_url = job.meta.get("webhook_url", "") if isinstance(job.meta, dict) else ""
    if not webhook_url:
        return
    enqueued_at = job.enqueued_at.isoformat() if job.enqueued_at else ""
    fire_webhook(
        url=webhook_url,
        job_id=job.id,
        status=status,
        enqueued_at=enqueued_at,
        completed_at=_get_completed_at(),
    )


def on_job_complete(job: "Job", connection, result, *args, **kwargs) -> None:
    """
    Called by RQ after a job succeeds.
    Clears the dedup key and fires webhook if configured.
    """
    dedup_key = job.meta.get("dedup_key", "") if isinstance(job.meta, dict) else ""
    if dedup_key:
        clear_dedup_key(dedup_key, connection)
    _fire_webhook_if_configured(job, "finished")


def on_job_failure(job: "Job", connection, type, value, traceback) -> None:
    """
    Called by RQ after a job fails.
    Clears the dedup key and fires webhook if configured.
    """
    dedup_key = job.meta.get("dedup_key", "") if isinstance(job.meta, dict) else ""
    if dedup_key:
        clear_dedup_key(dedup_key, connection)
    _fire_webhook_if_configured(job, "failed")
