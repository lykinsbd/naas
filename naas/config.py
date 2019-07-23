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
REDIS_HOST = os.environ.get("REDIS_MASTER_SERVICE_HOST", "redis")
REDIS_PORT = 6379


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
    if app.config["APP_ENVIRONMENT"].lower() == "dev":

        # Today we're not differentiating on environment...
        pass

    elif app.config["APP_ENVIRONMENT"].lower() == "staging":

        # Today we're not differentiating on environment...
        pass

    elif app.config["APP_ENVIRONMENT"].lower() == "production":

        # Today we're not differentiating on environment...
        pass

    # Turn off JSON Key sorting
    app.config["JSON_SORT_KEYS"] = False

    # Initialize a Redis connection and store it for later
    redis = Redis(host="redis")
    app.config["redis"] = redis

    # Create a random string to use as a Salt for the UN/PW hashes, stash it in redis
    redis.set("salt", "".join(random.choice(string.ascii_lowercase) for _ in range(10)))

    # Initialize an rq Queue and store it for later
    q = Queue("naas", connection=redis)
    app.config["q"] = q
