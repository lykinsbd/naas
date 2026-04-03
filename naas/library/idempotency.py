"""
idempotency.py
Client-controlled idempotency key support via X-Idempotency-Key header.
"""

import hashlib
from typing import TYPE_CHECKING

from naas.config import IDEMPOTENCY_TTL

if TYPE_CHECKING:
    from redis import Redis


def _redis_key(raw_key: str) -> str:
    """Hash the raw key before storage to avoid leaking sensitive values."""
    return f"naas:idempotency:{hashlib.sha256(raw_key.encode()).hexdigest()}"


def get_idempotent_job_id(key: str, redis: "Redis") -> str | None:
    """
    Return the existing job_id for this idempotency key, or None if not seen before.

    Args:
        key: Raw idempotency key from X-Idempotency-Key header
        redis: Redis connection

    Returns:
        Existing job_id string if key was seen within TTL, else None
    """
    stored = redis.get(_redis_key(key))
    if stored is None:
        return None
    return stored.decode() if isinstance(stored, bytes) else str(stored)


def store_idempotency_key(key: str, job_id: str, redis: "Redis") -> None:
    """
    Store the idempotency key → job_id mapping with TTL.

    Args:
        key: Raw idempotency key from X-Idempotency-Key header
        job_id: Job ID to associate with this key
        redis: Redis connection
    """
    redis.set(_redis_key(key), job_id, ex=IDEMPOTENCY_TTL, nx=True)
