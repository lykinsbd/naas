# API Resources

import time

from flask import current_app
from flask_restful import Resource
from redis.exceptions import RedisError

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

        overall = "healthy" if redis_status == "healthy" else "degraded"

        return {
            "status": overall,
            "version": __version__,
            "uptime_seconds": int(time.time() - _START_TIME),
            "components": {
                "redis": {"status": redis_status},
                "queue": {"status": "healthy", "depth": len(q)},
            },
        }
