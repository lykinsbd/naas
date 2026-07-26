"""Batch storage layer for bulk operations.

Stores batch metadata in Redis hashes with TTL. Each batch maps
a batch_id to its constituent job_ids and hosts for aggregate status queries.

Redis key: naas:batch:{batch_id}
Fields:
    jobs: JSON list of {"job_id": str, "host": str} mappings
    created_at: ISO 8601 timestamp
    hash: SHA-512 credential hash (for ownership validation)
"""

from __future__ import annotations

import json
import time
from uuid import uuid4

from redis import Redis

from naas.config import JOB_TTL_SUCCESS

BATCH_KEY_PREFIX = "naas:batch:"


def generate_batch_id() -> str:
    """Generate a unique batch identifier."""
    return f"batch-{uuid4().hex[:12]}"


def store_batch(
    redis: Redis,
    batch_id: str,
    jobs: list[dict[str, str]],
    salted_hash: str,
) -> None:
    """Store batch metadata in Redis.

    Args:
        redis: Redis connection.
        batch_id: Unique batch identifier.
        jobs: List of {"job_id": ..., "host": ...} mappings.
        salted_hash: SHA-512 hash of caller credentials (for ownership).
    """
    key = f"{BATCH_KEY_PREFIX}{batch_id}"
    redis.hset(
        key,
        mapping={
            "jobs": json.dumps(jobs),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hash": salted_hash,
        },
    )
    redis.expire(key, JOB_TTL_SUCCESS)


def get_batch(redis: Redis, batch_id: str) -> dict | None:
    """Retrieve batch metadata from Redis.

    Args:
        redis: Redis connection.
        batch_id: Batch identifier to look up.

    Returns:
        Dict with 'jobs' (list), 'created_at' (str), 'hash' (str),
        or None if the batch doesn't exist / has expired.
    """
    key = f"{BATCH_KEY_PREFIX}{batch_id}"
    data: dict[bytes, bytes] = redis.hgetall(key)  # type: ignore[assignment]
    if not data:
        return None

    return {
        "jobs": json.loads(data[b"jobs"].decode()),
        "created_at": data[b"created_at"].decode(),
        "hash": data[b"hash"].decode(),
    }


def validate_batch_ownership(batch_data: dict, salted_hash: str) -> bool:
    """Check if the caller owns this batch.

    Args:
        batch_data: Batch metadata from get_batch().
        salted_hash: SHA-512 hash of the current caller's credentials.

    Returns:
        True if the caller is the batch submitter.
    """
    return batch_data.get("hash", "") == salted_hash  # type: ignore[no-any-return]
