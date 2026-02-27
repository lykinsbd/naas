# API Resources

import time

from flask import current_app
from flask_restful import Resource
from redis.exceptions import RedisError
from rq import Worker

from naas import __version__

_START_TIME = time.time()


class HealthCheck(Resource):
    def get(self):
        """Return detailed health status including component checks."""
        redis = current_app.config["redis"]
        q = current_app.config["q"]

        # Check Redis connectivity
        try:
            redis.ping()
            redis_status = "healthy"
        except RedisError:
            redis_status = "unhealthy"

        # Check workers
        workers = Worker.all(connection=redis) if redis_status == "healthy" else []
        worker_count = len(workers)
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
