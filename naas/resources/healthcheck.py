# API Resources

import time

from flask import current_app
from flask_restful import Resource
from redis.exceptions import RedisError

from naas import __version__
from naas.library.worker_cache import get_cached_workers

_START_TIME = time.time()


class HealthCheck(Resource):
    def get(self):
        """Return detailed health status including component checks.

        Returns:
            dict: Health status with the following structure:
                {
                    "status": str,  # "healthy", "degraded", or "no_workers"
                    "version": str,  # NAAS version
                    "uptime_seconds": int,  # Seconds since API start
                    "components": {
                        "redis": {"status": str},  # "healthy" or "unhealthy"
                        "queue": {"status": str, "depth": int},  # Queue status and job count
                        "workers": {
                            "status": str,  # "healthy" or "no_workers"
                            "count": int,  # Number of worker pods/hosts
                            "active_jobs": int  # Jobs currently processing
                        }
                    }
                }
        """
        redis = current_app.config["redis"]
        q = current_app.config["q"]

        # Check Redis connectivity
        try:
            redis.ping()
            redis_status = "healthy"
        except RedisError:
            redis_status = "unhealthy"

        # Check workers — count unique hostnames (pods/hosts), not individual processes
        workers = get_cached_workers(redis) if redis_status == "healthy" else []
        worker_count = len({w.hostname for w in workers})
        active_jobs = sum(1 for w in workers if w.get_current_job() is not None)
        worker_status = "healthy" if worker_count > 0 else "no_workers"

        if redis_status != "healthy":
            overall = "degraded"
        elif worker_count == 0:
            overall = "no_workers"
        else:
            overall = "healthy"

        return {
            "status": overall,
            "version": __version__,
            "uptime_seconds": int(time.time() - _START_TIME),
            "components": {
                "redis": {"status": redis_status},
                "queue": {"status": "healthy", "depth": len(q)},
                "workers": {"status": worker_status, "count": worker_count, "active_jobs": active_jobs},
            },
        }
