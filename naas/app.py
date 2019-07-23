#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
 app.py
 Author: Brett Lykins (lykinsbd@gmail.com)
 Description: Main app setup/config
"""

import logging

from flask import Flask
from flask_restful import Api
from naas.config import app_configure
from naas.library.errorhandlers import api_error_generator
from naas.resources.get_results import GetResults
from naas.resources.healthcheck import HealthCheck
from naas.resources.send_command import SendCommand


app = Flask(__name__)

app_configure(app)

# Setup logging:
logger = logging.getLogger(name="NAAS")
app.logger.handlers = logger.handlers
app.logger.setLevel(logger.level)

# Get the error handling dict
api_errors = api_error_generator()

# Instantiate your API
api = Api(app, errors=api_errors, catch_all_404s=True)

# Add resources (wrappers for Flask views)
api.add_resource(HealthCheck, "/", "/healthcheck")
api.add_resource(SendCommand, "/send_command")
api.add_resource(GetResults, "/send_command/<string:job_id>")
