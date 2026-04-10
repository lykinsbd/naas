"""Prometheus metrics for RQ worker processes.

Uses prometheus_client multiprocess mode so child worker processes
can write metrics and the main process serves them via HTTP.
"""

import os
import tempfile

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, multiprocess

# Multiprocess shared directory — set before any metric is created.
# The main process calls init() to configure this.
_multiproc_dir: str = ""


def init() -> str:
    """Initialize multiprocess metrics directory. Returns the path."""
    global _multiproc_dir
    _multiproc_dir = tempfile.mkdtemp(prefix="naas_metrics_")
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = _multiproc_dir
    return _multiproc_dir


def make_registry() -> CollectorRegistry:
    """Create a registry that collects from all worker processes."""
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return registry


# -- Metrics (created lazily in child processes after env var is set) --

jobs_total = Counter(
    "naas_worker_jobs_total",
    "Total jobs processed by workers",
    ["status", "context"],
)

job_duration_seconds = Histogram(
    "naas_worker_job_duration_seconds",
    "Job execution duration in seconds",
    ["platform", "context"],
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)

active_jobs = Gauge(
    "naas_worker_active_jobs",
    "Currently executing jobs",
    multiprocess_mode="livesum",
)
