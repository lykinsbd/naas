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
CERT_KEY_FILE = "/app/key.pem"
CERT_FILE = "/app/cert.crt"
CERT_BUNDLE_FILE = "/app/bundle.crt"

# Redis config
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "mah_redis_pw")

# Job TTL config (seconds)
JOB_TTL_SUCCESS = int(os.environ.get("JOB_TTL_SUCCESS", 86400))  # 24h
JOB_TTL_FAILED = int(os.environ.get("JOB_TTL_FAILED", 604800))  # 7 days

# Circuit breaker config
CIRCUIT_BREAKER_ENABLED = os.environ.get("CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"
CIRCUIT_BREAKER_THRESHOLD = int(os.environ.get("CIRCUIT_BREAKER_THRESHOLD", 5))
CIRCUIT_BREAKER_TIMEOUT = int(os.environ.get("CIRCUIT_BREAKER_TIMEOUT", 300))  # 5 minutes

# Graceful shutdown config (seconds)
SHUTDOWN_TIMEOUT = int(os.environ.get("SHUTDOWN_TIMEOUT", 30))  # 30s


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
    app.config["redis"] = redis

    # Create a random string to use as a Salt for the UN/PW hashes, stash it in redis
    redis.set("naas_cred_salt", "".join(random.choice(string.ascii_lowercase) for _ in range(10)))

    # Initialize an rq Queue and store it for later
    q = Queue("naas", connection=redis)
    app.config["q"] = q
