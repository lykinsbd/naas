"""
reaper.py
Background thread that detects orphaned jobs from dead workers and moves them
to the FailedJobRegistry. Runs in each worker process but uses a distributed
Redis lock so only one reaper executes per cycle.
"""

import logging
import threading
import time
from typing import TYPE_CHECKING

from rq import Worker
from rq.job import Job, JobStatus
from rq.registry import FailedJobRegistry, StartedJobRegistry
from rq.worker import BaseWorker

from naas.config import JOB_REAPER_ENABLED, JOB_REAPER_INTERVAL, WORKER_STALE_THRESHOLD
from naas.library.dedup import clear_dedup_key

if TYPE_CHECKING:
    from redis import Redis

logger = logging.getLogger(__name__)

_REAPER_LOCK_KEY = "naas:reaper:lock"


def _is_worker_stale(worker: BaseWorker, threshold: int) -> bool:
    """Return True if the worker's last heartbeat exceeds the stale threshold."""
    last_heartbeat = worker.last_heartbeat
    if last_heartbeat is None:
        return True
    age = time.time() - last_heartbeat.timestamp()
    return bool(age > threshold)


def reap_orphaned_jobs(redis: "Redis") -> int:
    """
    Scan StartedJobRegistry for jobs whose worker is dead or stale.
    Move orphaned jobs to FailedJobRegistry and clear their dedup keys.

    Returns the number of jobs reaped.
    """
    worker_id = f"reaper-{threading.get_ident()}"

    # Acquire distributed lock — only one reaper runs per cycle
    acquired = redis.set(_REAPER_LOCK_KEY, worker_id, nx=True, ex=JOB_REAPER_INTERVAL)
    if not acquired:
        return 0

    reaped = 0
    try:
        started_registry = StartedJobRegistry(connection=redis)
        failed_registry = FailedJobRegistry(connection=redis)
        active_workers = {w.name: w for w in Worker.all(connection=redis)}

        for job_id in started_registry.get_job_ids():
            try:
                job = Job.fetch(job_id, connection=redis)
            except Exception:
                continue

            worker_name = job.worker_name
            worker = active_workers.get(worker_name) if worker_name else None

            if worker is None or _is_worker_stale(worker, WORKER_STALE_THRESHOLD):
                logger.warning("Reaper: orphaned job %s (worker %s dead/stale)", job_id, worker_name)

                # Clear dedup key so the job can be re-submitted
                dedup_key = job.meta.get("dedup_key", "") if isinstance(job.meta, dict) else ""
                if dedup_key:
                    clear_dedup_key(dedup_key, redis)

                # Move to failed registry
                started_registry.remove(job)
                failed_registry.add(job, exc_string=f"Worker {worker_name} died or became unresponsive")
                job.set_status(JobStatus.FAILED)

                from naas.library.audit import emit_audit_event  # avoid circular import

                emit_audit_event("job.orphaned", request_id=job_id, worker_name=worker_name or "unknown")

                reaped += 1

    finally:
        redis.delete(_REAPER_LOCK_KEY)

    if reaped:
        logger.info("Reaper: reaped %d orphaned job(s)", reaped)
    return reaped


def start_reaper(redis: "Redis") -> threading.Thread:
    """
    Start the reaper as a background daemon thread.

    Args:
        redis: Redis connection

    Returns:
        The started thread
    """
    if not JOB_REAPER_ENABLED:
        logger.info("Job reaper disabled (JOB_REAPER_ENABLED=false)")
        return threading.Thread()  # Return a no-op thread

    def _run() -> None:
        logger.info(
            "Job reaper started (interval=%ds, stale_threshold=%ds)", JOB_REAPER_INTERVAL, WORKER_STALE_THRESHOLD
        )
        while True:
            time.sleep(JOB_REAPER_INTERVAL)
            try:
                reap_orphaned_jobs(redis)
            except Exception as e:
                logger.error("Reaper error: %s", e)

    thread = threading.Thread(target=_run, daemon=True, name="naas-reaper")
    thread.start()
    return thread
