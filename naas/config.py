#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
 config.py
 Author: Brett Lykins (lykinsbd@gmail.com)
 Description: Configure NAAS API
"""

import os

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

    app.config.from_object(_DefaultSettings)

    if app.config["APP_ENVIRONMENT"].lower() == "dev":

        # Today we're not differentiating on environment...
        pass

    elif app.config["APP_ENVIRONMENT"].lower() == "staging":

        # Today we're not differentiating on environment...
        pass

    elif app.config["APP_ENVIRONMENT"].lower() == "production":

        # Today we're not differentiating on environment...
        pass

    q = Queue("naas", connection=Redis(host="redis"))
    app.config["q"] = q


class _DefaultSettings(object):
    """Set base variables based on deployment"""

    VALID_ENVIRONMENTS = ["dev", "staging", "production"]
    APP_ENVIRONMENT = os.environ.get("APP_ENVIRONMENT", "dev")

    """Default set the env to "dev" if something invalid is specified"""
    if APP_ENVIRONMENT.lower() not in VALID_ENVIRONMENTS:
        APP_ENVIRONMENT = "dev"

    """Disable flask debugger"""
    DEBUG = False

    LOG_LEVELS = {"CRITICAL": 50, "ERROR": 40, "WARNING": 30, "INFO": 20, "DEBUG": 10, "NOTSET": 0}

    if "dev" in APP_ENVIRONMENT:
        LOG_LEVEL = LOG_LEVELS.get(os.environ.get("LOG_LEVEL", "DEBUG"), "DEBUG")
    else:
        LOG_LEVEL = LOG_LEVELS.get(os.environ.get("LOG_LEVEL", "INFO"), "INFO")
