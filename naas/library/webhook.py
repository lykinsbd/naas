"""
webhook.py
HTTP POST notification on job completion with retry support.
Payload contains only job metadata — never results or credentials.
"""

import hashlib
import hmac
import json
import logging

import requests

from naas.config import WEBHOOK_TIMEOUT

logger = logging.getLogger(__name__)


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    return "sha256=" + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


class WebhookDeliveryError(Exception):
    """Raised when webhook delivery fails (triggers RQ retry)."""


def deliver_webhook(url: str, job_id: str, status: str, enqueued_at: str, completed_at: str, secret: str = "") -> None:
    """POST a job completion notification. Raises on failure for RQ retry.

    Args:
        url: HTTPS URL to POST to
        job_id: RQ job ID
        status: Job status string (e.g. "finished", "failed")
        enqueued_at: ISO 8601 enqueue timestamp
        completed_at: ISO 8601 completion timestamp
        secret: Optional shared secret for HMAC-SHA256 signing
    """
    payload = {
        "job_id": job_id,
        "status": status,
        "enqueued_at": enqueued_at,
        "completed_at": completed_at,
    }
    headers: dict[str, str] = {"X-NAAS-Delivery": job_id}
    if secret:
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        headers["X-NAAS-Signature"] = _sign_payload(payload_bytes, secret)
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=WEBHOOK_TIMEOUT)
        response.raise_for_status()
        logger.info("Webhook delivered: job_id=%s url=%s status=%d", job_id, url, response.status_code)
    except Exception as e:
        logger.warning("Webhook delivery failed: job_id=%s url=%s error=%s", job_id, url, e)
        raise WebhookDeliveryError(str(e)) from e
