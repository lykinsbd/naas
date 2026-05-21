#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
app.py
Author: Brett Lykins (lykinsbd@gmail.com)
Description: Main app setup/config
"""

import logging
import os

from flask import Flask, g, jsonify, request
from flask_restful import Api
from prometheus_client import Gauge
from prometheus_flask_exporter import PrometheusMetrics
from pythonjsonlogger.json import JsonFormatter
from redis.exceptions import RedisError

from naas import __base_response__
from naas.config import app_configure
from naas.library.errorhandlers import api_error_generator
from naas.library.otel import OTEL_ENABLED, init_telemetry
from naas.library.worker_cache import get_cached_workers
from naas.resources.api_keys import ApiKey, ApiKeyRotate, ApiKeys
from naas.resources.cancel_job import CancelJob
from naas.resources.contexts import Contexts
from naas.resources.failed_jobs import FailedJobs, ReplayJob
from naas.resources.get_results import GetResults
from naas.resources.healthcheck import HealthCheck
from naas.resources.list_jobs import ListJobs
from naas.resources.send_command import SendCommand
from naas.resources.send_command_structured import SendCommandStructured
from naas.resources.send_config import SendConfig
from naas.resources.stream_job import StreamJob
from naas.spec import spec

app = Flask(__name__)

# Initialize OpenTelemetry (no-op when OTEL_ENABLED=false)
init_telemetry(service_name="naas-api")
if OTEL_ENABLED:  # pragma: no cover — tested via integration tests with OTEL_ENABLED=true
    from opentelemetry.instrumentation.flask import FlaskInstrumentor

    FlaskInstrumentor().instrument_app(app)

app_configure(app)


@app.errorhandler(RedisError)
def handle_redis_error(e: RedisError):
    """Return 503 for any Redis connectivity failure without leaking internal details."""
    app.logger.error("Redis error: %s", type(e).__name__)
    response = jsonify({"error": "Queue backend unavailable", "status": 503, **__base_response__})
    response.status_code = 503
    response.headers["Retry-After"] = "10"
    return response


# Prometheus metrics — request counts/latency via exporter, NAAS-specific gauges manually updated
metrics = PrometheusMetrics(app, path="/metrics", default_labels={"app": "naas"})
_queue_depth = Gauge("naas_queue_depth", "Number of jobs waiting in queue")
_workers_active = Gauge("naas_workers_active", "Number of active RQ workers")
_failed_jobs = Gauge("naas_failed_jobs_total", "Number of jobs in the failed registry")


@app.before_request
def _update_queue_metrics() -> None:
    """Refresh queue/worker gauges on each request."""
    q = app.config.get("q")
    redis = app.config.get("redis")
    if q is not None:
        _queue_depth.set(len(q))
    if redis is not None:
        _workers_active.set(len(get_cached_workers(redis)))
        from rq.registry import FailedJobRegistry

        _failed_jobs.set(len(FailedJobRegistry(connection=redis)))


# Structured JSON logging
_handler = logging.StreamHandler()
_handler.setFormatter(
    JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
)
logging.root.handlers = [_handler]
logging.root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

logger = logging.getLogger(name="NAAS")
app.logger.handlers = logger.handlers
app.logger.setLevel(logger.level)

# Get the error handling dict
api_errors = api_error_generator()

# Instantiate your API
api = Api(app, errors=api_errors, catch_all_404s=True)

# Versioned routes (canonical)
api.add_resource(HealthCheck, "/", "/healthcheck", "/v1/healthcheck")
api.add_resource(SendCommand, "/v1/send_command")
api.add_resource(SendCommandStructured, "/v1/send_command_structured")
api.add_resource(SendConfig, "/v1/send_config")
api.add_resource(
    GetResults,
    "/v1/send_command/<string:job_id>",
    "/v1/send_config/<string:job_id>",
    "/v1/send_command_structured/<string:job_id>",
)
api.add_resource(ListJobs, "/v1/jobs")
api.add_resource(FailedJobs, "/v1/jobs/failed")
api.add_resource(CancelJob, "/v1/jobs/<string:job_id>")
api.add_resource(ReplayJob, "/v1/jobs/<string:job_id>/replay")
api.add_resource(Contexts, "/v1/contexts")
api.add_resource(ApiKeys, "/v1/api-keys")
api.add_resource(ApiKey, "/v1/api-keys/<string:key_id>")
api.add_resource(ApiKeyRotate, "/v1/api-keys/<string:key_id>/rotate")

# v2 routes (hyphenated, RBAC/context auth enforced)
api.add_resource(SendCommand, "/v2/send-command", endpoint="send_command_v2")
api.add_resource(SendCommandStructured, "/v2/send-command-structured", endpoint="send_command_structured_v2")
api.add_resource(SendConfig, "/v2/send-config", endpoint="send_config_v2")
api.add_resource(
    GetResults,
    "/v2/send-command/<string:job_id>",
    "/v2/send-config/<string:job_id>",
    "/v2/send-command-structured/<string:job_id>",
    endpoint="get_results_v2",
)
api.add_resource(ListJobs, "/v2/jobs", endpoint="list_jobs_v2")
api.add_resource(FailedJobs, "/v2/jobs/failed", endpoint="failed_jobs_v2")
api.add_resource(CancelJob, "/v2/jobs/<string:job_id>", endpoint="cancel_job_v2")
api.add_resource(ReplayJob, "/v2/jobs/<string:job_id>/replay", endpoint="replay_job_v2")
api.add_resource(StreamJob, "/v2/jobs/<string:job_id>/stream", endpoint="stream_job_v2")
api.add_resource(Contexts, "/v2/contexts", endpoint="contexts_v2")
api.add_resource(ApiKeys, "/v2/api-keys", endpoint="api_keys_v2")
api.add_resource(ApiKey, "/v2/api-keys/<string:key_id>", endpoint="api_key_v2")
api.add_resource(ApiKeyRotate, "/v2/api-keys/<string:key_id>/rotate", endpoint="api_key_rotate_v2")

# Legacy unversioned routes (deprecated aliases — kept for backward compatibility)
_DEPRECATED_PREFIXES = ("/v1/", "/send_command", "/send_config", "/healthcheck")

# Sunset date for /v1/ and unversioned routes (RFC 8594 Sunset header).
# This is a public commitment to API clients communicated since v2.0.
# DO NOT change this value without explicit team decision and a corresponding
# entry in the changelog. The actual removal is tracked by the v3.0 milestone.
# See: docs/upgrading.md, docs/adr/0007-api-versioning-strategy.md
_DEPRECATION_SUNSET_DATE = "2027-01-01"


@app.after_request
def add_version_headers(response):
    """Inject API version and deprecation headers on every response."""
    if request.path.startswith("/v2/"):
        response.headers["X-API-Version"] = "v2"
    elif request.path.startswith("/v1/"):
        response.headers["X-API-Version"] = "v1"
    if request.path.startswith(_DEPRECATED_PREFIXES):
        response.headers["X-API-Deprecated"] = "true"
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = _DEPRECATION_SUNSET_DATE
        response.headers["Link"] = '</v2/>; rel="successor-version"'
    # Rate limit headers
    if hasattr(g, "rate_limit_limit"):
        response.headers["X-RateLimit-Limit"] = str(g.rate_limit_limit)
        response.headers["X-RateLimit-Remaining"] = str(g.rate_limit_remaining)
        response.headers["X-RateLimit-Reset"] = str(g.rate_limit_reset)
    return response


# Register legacy routes on the same resources (after after_request is defined)
api.add_resource(SendCommand, "/send_command", endpoint="send_command_legacy")
api.add_resource(SendConfig, "/send_config", endpoint="send_config_legacy")
api.add_resource(
    GetResults,
    "/send_command/<string:job_id>",
    "/send_config/<string:job_id>",
    endpoint="get_results_legacy",
)

spec.register(app)
