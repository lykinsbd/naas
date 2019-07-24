#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

from flask import current_app, g, request
from functools import wraps
from naas.library import validation
from uuid import uuid4


def valid_post(f):
    """
    Decorator function to check validity of a NAAS payload
    :param f:
    :return:
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        v = validation.Validate()
        v.is_json()
        v.is_ip_addr(request.json["ip"], "ip")
        v.is_command_set()
        v.custom_port()
        v.has_platform()

        # Capture or create the x-request-id
        if "x-request-id" not in v.http.headers.keys():
            g.request_id = str(uuid4())
        else:
            v.is_uuid(uuid=v.http.headers["x-request-id"])
            g.request_id = v.http.headers["x-request-id"]

        # Log this request's details
        current_app.logger.info(
            "%s: %s is issuing %s command(s) to %s:%s",
            g.request_id,
            request.authorization.username,
            len(request.json["commands"]),
            request.json["ip"],
            request.json["port"],
        )
        current_app.logger.debug(
            "%s: %s is issuing the following commands to %s:%s: %s",
            g.request_id,
            request.authorization.username,
            request.json["ip"],
            request.json["port"],
            request.json["commands"],
        )
        return f(*args, **kwargs)

    return wrapper
