#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
app.py
Author: Brett Lykins (lykinsbd@gmail.com)
Description: Main app setup/config
"""

import logging
import os

from flask import Flask, request
from flask_restful import Api
from prometheus_client import Gauge
from prometheus_flask_exporter import PrometheusMetrics
from pythonjsonlogger.json import JsonFormatter

from naas.config import app_configure
from naas.library.errorhandlers import api_error_generator
from naas.resources.get_results import GetResults
from naas.resources.healthcheck import HealthCheck
from naas.resources.list_jobs import ListJobs
from naas.resources.send_command import SendCommand
from naas.resources.send_config import SendConfig
from naas.spec import spec

app = Flask(__name__)

app_configure(app)

# Prometheus metrics — request counts/latency via exporter, NAAS-specific gauges manually updated
metrics = PrometheusMetrics(app, path="/metrics", default_labels={"app": "naas"})
_queue_depth = Gauge("naas_queue_depth", "Number of jobs waiting in queue")
_workers_active = Gauge("naas_workers_active", "Number of active RQ workers")


@app.before_request
def _update_queue_metrics() -> None:
    """Refresh queue/worker gauges on each request."""
    q = app.config.get("q")
    redis = app.config.get("redis")
    if q is not None:
        _queue_depth.set(len(q))
    if redis is not None:
        from rq import Worker

        _workers_active.set(len(Worker.all(connection=redis)))


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
api.add_resource(SendConfig, "/v1/send_config")
api.add_resource(GetResults, "/v1/send_command/<string:job_id>", "/v1/send_config/<string:job_id>")
api.add_resource(ListJobs, "/v1/jobs")

# Legacy unversioned routes (deprecated aliases — kept for backward compatibility)
_LEGACY_PREFIXES = ("/send_command", "/send_config")


@app.after_request
def add_version_headers(response):
    """Inject X-API-Version and deprecation headers on every response."""
    response.headers["X-API-Version"] = "v1"
    if request.path.startswith(_LEGACY_PREFIXES):
        response.headers["X-API-Deprecated"] = "true"
        response.headers["X-API-Sunset"] = "2027-01-01"
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
