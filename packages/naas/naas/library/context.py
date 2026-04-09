"""
context.py
Context routing helpers for multi-segment worker environments.
"""

from rq import Queue, Worker

from naas.config import MAX_QUEUE_DEPTH, NAAS_CONTEXTS
from naas.library.errorhandlers import InvalidContext, NoWorkersForContext, QueueFull


def get_queue_for_context(context: str, redis: object) -> Queue:
    """
    Return the RQ Queue for the given context, validating it first.

    Args:
        context: Context name from request
        redis: Redis connection

    Returns:
        RQ Queue for the context

    Raises:
        InvalidContext: If context is not in NAAS_CONTEXTS
        NoWorkersForContext: If no active workers serve this context
    """
    if context not in NAAS_CONTEXTS:
        raise InvalidContext

    queue_name = f"naas-{context}"
    q = Queue(queue_name, connection=redis)  # type: ignore[arg-type]

    # Check for active workers serving this context
    active_workers = [w for w in Worker.all(connection=redis) if queue_name in w.queue_names()]  # type: ignore[arg-type]
    if not active_workers:
        raise NoWorkersForContext

    if MAX_QUEUE_DEPTH > 0 and len(q) >= MAX_QUEUE_DEPTH:
        raise QueueFull

    return q
