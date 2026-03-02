"""Cached Worker.all() helper to avoid repeated Redis scans on every request."""

import time

from rq import Worker

_cache: list = []
_cache_ts: float = 0.0
_TTL = 10.0  # seconds


def get_cached_workers(redis) -> list:  # type: ignore[type-arg]
    """Return cached Worker.all() result, refreshing if TTL expired.

    Args:
        redis: Redis connection.

    Returns:
        List of RQ Worker objects, cached for up to 10 seconds.
    """
    global _cache, _cache_ts
    now = time.monotonic()
    if now - _cache_ts > _TTL:
        _cache = Worker.all(connection=redis)
        _cache_ts = now
    return _cache
