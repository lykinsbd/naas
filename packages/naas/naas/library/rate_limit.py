"""Per-caller sliding window rate limiter backed by Redis sorted sets.

Uses the same pattern as ``_is_locked_out()`` in ``auth.py``: a sorted set
per key with timestamps as scores, pruned on each check.
"""

from __future__ import annotations

import time
from functools import wraps
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from flask import g, request

from naas import __base_response__
from naas.config import (
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_EXEMPT_ROLES,
    RATE_LIMIT_PER_CALLER,
    RATE_LIMIT_PER_CALLER_DEVICE,
    RATE_LIMIT_WINDOW,
)

if TYPE_CHECKING:
    from redis import Redis


def _check_limit(redis_key: str, limit: int, window: int, redis: Redis) -> tuple[int, int]:
    """Record a request and return (count, remaining).

    Uses a Redis sorted set with timestamp scores.  Old entries outside the
    window are pruned on every call.
    """
    now = time.time()
    pipe = redis.pipeline()
    pipe.zremrangebyscore(redis_key, 0, now - window)
    pipe.zadd(redis_key, {str(uuid4()): now})
    pipe.expire(redis_key, window)
    pipe.zcard(redis_key)
    results = pipe.execute()
    count: int = results[3]
    return count, max(0, limit - count)


def _get_caller_id() -> str:
    """Extract caller identity from Flask ``g``."""
    if getattr(g, "auth_method", None) == "bearer":
        return str(g.jwt_claims.get("sub", "unknown"))
    if hasattr(g, "credentials"):
        return str(g.credentials.username)
    return request.remote_addr or "unknown"


def _is_exempt() -> bool:
    """Return True if the current caller's role is exempt from rate limits."""
    if getattr(g, "auth_method", None) == "basic":
        return True  # basic auth users are implicitly admin
    role = getattr(g, "jwt_claims", {}).get("role", "viewer")
    return role in RATE_LIMIT_EXEMPT_ROLES


def check_rate_limit(caller_id: str, device: str | None, redis: Redis) -> dict | None:
    """Check both per-caller and per-caller-per-device limits.

    Stores rate limit metadata on ``g`` for response headers.

    Returns:
        None if allowed, or a 429 response body dict if rate-limited.
    """
    # Per-caller global
    key = f"naas:rl:{caller_id}"
    count, remaining = _check_limit(key, RATE_LIMIT_PER_CALLER, RATE_LIMIT_WINDOW, redis)
    g.rate_limit_limit = RATE_LIMIT_PER_CALLER
    g.rate_limit_remaining = remaining
    g.rate_limit_reset = int(time.time()) + RATE_LIMIT_WINDOW
    if count > RATE_LIMIT_PER_CALLER:
        return {"error": "Rate limit exceeded", "retry_after": RATE_LIMIT_WINDOW, **__base_response__}

    # Per-caller-per-device
    if device:
        dev_key = f"naas:rl:{caller_id}:{device}"
        dev_count, dev_remaining = _check_limit(dev_key, RATE_LIMIT_PER_CALLER_DEVICE, RATE_LIMIT_WINDOW, redis)
        if dev_count > RATE_LIMIT_PER_CALLER_DEVICE:
            g.rate_limit_limit = RATE_LIMIT_PER_CALLER_DEVICE
            g.rate_limit_remaining = 0
            return {"error": "Rate limit exceeded", "retry_after": RATE_LIMIT_WINDOW, **__base_response__}
        # Report the tighter remaining of the two
        if dev_remaining < remaining:
            g.rate_limit_limit = RATE_LIMIT_PER_CALLER_DEVICE
            g.rate_limit_remaining = dev_remaining

    return None


def rate_limited(f: Any) -> Any:
    """Decorator that enforces rate limits on submission endpoints."""

    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not RATE_LIMIT_ENABLED:
            return f(*args, **kwargs)
        if _is_exempt():
            return f(*args, **kwargs)

        from flask import current_app

        redis = current_app.config["redis"]
        caller_id = _get_caller_id()
        body = request.get_json(silent=True) or {}
        device = body.get("host") or body.get("ip")
        result = check_rate_limit(caller_id, device, redis)
        if result is not None:
            return result, 429, {"Retry-After": str(RATE_LIMIT_WINDOW)}
        return f(*args, **kwargs)

    return wrapper
