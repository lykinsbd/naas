"""
webhook.py
Fire-and-forget HTTP POST notification on job completion.
Payload contains only job metadata — never results or credentials.
"""

import logging

import requests

logger = logging.getLogger(__name__)

_WEBHOOK_TIMEOUT = 10  # seconds


def fire_webhook(url: str, job_id: str, status: str, enqueued_at: str, completed_at: str) -> None:
    """
    POST a job completion notification to the given URL.

    Fire-and-forget: errors are logged but never propagate to the caller.
    The payload contains only job metadata — results and credentials are never included.

    Args:
        url: HTTPS URL to POST to
        job_id: RQ job ID
        status: Job status string (e.g. "finished", "failed")
        enqueued_at: ISO 8601 enqueue timestamp
        completed_at: ISO 8601 completion timestamp
    """
    payload = {
        "job_id": job_id,
        "status": status,
        "enqueued_at": enqueued_at,
        "completed_at": completed_at,
    }
    try:
        response = requests.post(url, json=payload, timeout=_WEBHOOK_TIMEOUT)
        response.raise_for_status()
        logger.info("Webhook delivered: job_id=%s url=%s status=%d", job_id, url, response.status_code)
    except Exception as e:
        logger.warning("Webhook delivery failed: job_id=%s url=%s error=%s", job_id, url, e)
