"""
callbacks.py
RQ job callbacks for post-job cleanup (dedup key deletion, etc.)
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rq.job import Job


def on_job_complete(job: "Job", connection, result, *args, **kwargs) -> None:
    """
    Called by RQ after a job succeeds or fails.
    Clears the dedup key so the same job can be re-submitted.
    """
    dedup_key = job.meta.get("dedup_key", "")
    if dedup_key:
        connection.delete(dedup_key)


def on_job_failure(job: "Job", connection, type, value, traceback) -> None:
    """
    Called by RQ after a job fails.
    Clears the dedup key so the same job can be re-submitted.
    """
    dedup_key = job.meta.get("dedup_key", "")
    if dedup_key:
        connection.delete(dedup_key)
