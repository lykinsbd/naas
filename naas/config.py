#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
config.py
Author: Brett Lykins (lykinsbd@gmail.com)
Description: Configure NAAS API
"""

import os
import random
import string

from redis import Redis
from rq import Queue

# Cert/Key File Locations
CERT_KEY_FILE = "/tmp/key.pem"
CERT_FILE = "/tmp/cert.pem"
CERT_BUNDLE_FILE = "/tmp/bundle.crt"

# Redis config
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "mah_redis_pw")

# Job TTL config (seconds)
JOB_TTL_SUCCESS = int(os.environ.get("JOB_TTL_SUCCESS", 86400))  # 24h
JOB_TTL_FAILED = int(os.environ.get("JOB_TTL_FAILED", 604800))  # 7 days
JOB_TIMEOUT = int(os.environ.get("JOB_TIMEOUT", 120))  # 2 minutes; covers delay_factor=1 + buffer

# Circuit breaker config
CIRCUIT_BREAKER_ENABLED = os.environ.get("CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"
CIRCUIT_BREAKER_THRESHOLD = int(os.environ.get("CIRCUIT_BREAKER_THRESHOLD", 5))
CIRCUIT_BREAKER_TIMEOUT = int(os.environ.get("CIRCUIT_BREAKER_TIMEOUT", 300))  # 5 minutes

# Graceful shutdown config (seconds)
SHUTDOWN_TIMEOUT = int(os.environ.get("SHUTDOWN_TIMEOUT", 30))  # 30s

# Connection pool config
CONNECTION_POOL_ENABLED = os.environ.get("CONNECTION_POOL_ENABLED", "true").lower() == "true"
CONNECTION_POOL_MAX_SIZE = int(os.environ.get("CONNECTION_POOL_MAX_SIZE", 10))
CONNECTION_POOL_IDLE_TIMEOUT = int(os.environ.get("CONNECTION_POOL_IDLE_TIMEOUT", 300))  # 5 minutes
CONNECTION_POOL_MAX_AGE = int(os.environ.get("CONNECTION_POOL_MAX_AGE", 3600))  # 1 hour
CONNECTION_POOL_KEEPALIVE = int(os.environ.get("CONNECTION_POOL_KEEPALIVE", 60))  # seconds
CONNECTION_POOL_EXCLUDE: frozenset[str] = frozenset(
    e.strip() for e in os.environ.get("CONNECTION_POOL_EXCLUDE", "").split(",") if e.strip()
)

# Context routing config
NAAS_CONTEXTS: frozenset[str] = frozenset(
    c.strip() for c in os.environ.get("NAAS_CONTEXTS", "default").split(",") if c.strip()
)
WORKER_CONTEXTS: list[str] = [c.strip() for c in os.environ.get("WORKER_CONTEXTS", "default").split(",") if c.strip()]

# Queue depth limit (0 = disabled)
MAX_QUEUE_DEPTH: int = int(os.environ.get("MAX_QUEUE_DEPTH", 0))

# Idempotency key TTL in seconds (24h default)
IDEMPOTENCY_TTL: int = int(os.environ.get("IDEMPOTENCY_TTL", 86400))

# Job deduplication (enabled by default)
JOB_DEDUP_ENABLED: bool = os.environ.get("JOB_DEDUP_ENABLED", "true").lower() == "true"

# Webhook config
WEBHOOK_ALLOW_HTTP: bool = os.environ.get("WEBHOOK_ALLOW_HTTP", "false").lower() == "true"

# Job reaper config
JOB_REAPER_ENABLED: bool = os.environ.get("JOB_REAPER_ENABLED", "true").lower() == "true"
JOB_REAPER_INTERVAL: int = int(os.environ.get("JOB_REAPER_INTERVAL", 60))
WORKER_STALE_THRESHOLD: int = int(os.environ.get("WORKER_STALE_THRESHOLD", 120))


def app_configure(app):
    # Configure our environment
    app_environment = os.environ.get("APP_ENVIRONMENT", "dev")

    # Default set the env to "dev" if something invalid is specified
    if app_environment.lower() not in ["dev", "staging", "production"]:
        app_environment = "dev"

    app.config["APP_ENVIRONMENT"] = app_environment

    # Disable flask debugger
    app.config["DEBUG"] = False

    if "dev" in app.config["APP_ENVIRONMENT"]:
        app.config["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "DEBUG")
    else:
        app.config["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "INFO")

    # Push our log level up to an environment variable.
    os.environ["LOG_LEVEL"] = app.config["LOG_LEVEL"]

    # Configure environment specific variables
    if (
        app.config["APP_ENVIRONMENT"].lower() == "dev"
        or app.config["APP_ENVIRONMENT"].lower() == "staging"
        or app.config["APP_ENVIRONMENT"].lower() == "production"
    ):
        # Today we're not differentiating on environment...
        pass

    # Turn off JSON Key sorting
    app.config["JSON_SORT_KEYS"] = False

    # Initialize a Redis connection and store it for later
    redis = Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD)
    redis.ping()  # Fail fast if Redis is unavailable at startup
    app.config["redis"] = redis

    # Create a random string to use as a Salt for the UN/PW hashes, stash it in redis.
    # Use setnx so the salt persists across API restarts — overwriting it would invalidate
    # all connection pool keys and in-flight job auth checks.
    redis.setnx("naas_cred_salt", "".join(random.choice(string.ascii_lowercase) for _ in range(10)))

    # Initialize an rq Queue and store it for later (default context queue)
    q = Queue("naas-default", connection=redis)
    app.config["q"] = q
