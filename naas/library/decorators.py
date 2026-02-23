#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

from functools import wraps
from uuid import uuid4

from flask import current_app, g, request

from naas.library import validation
from naas.library.auth import Credentials


def valid_post(f):
    """
    Decorator function to check validity of a POSTed NAAS payload
    :param f:
    :return:
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        """
        Perform validation and other actions on this request and payload
        :param args:
        :param kwargs:
        :return:
        """

        v = validation.Validate()
        v.has_auth()
        v.locked_out()
        v.is_json()
        v.is_ip_addr()
        v.is_command_set()
        v.has_port()
        v.save_config()
        v.commit()
        v.has_platform()
        v.has_delay_factor()

        # Capture or create the x-request-id, and store it on the g object
        if "x-request-id" not in v.headers.keys():
            g.request_id = str(uuid4())
        else:
            v.is_uuid(uuid=v.headers["x-request-id"])
            g.request_id = v.headers["x-request-id"]

        # Validate if there's a job ID by this x-request-id already:
        v.is_duplicate_job(g.request_id)

        # Create a credentials object, and store it on the g object
        g.credentials = Credentials(
            username=request.authorization.username,
            password=request.authorization.password,
            enable=request.json.get("enable", None),
        )

        # Log this request's details
        current_app.logger.info(
            "%s: %s is issuing %s command(s) to %s:%s",
            g.request_id,
            g.credentials.username,
            len(request.json["commands"]),
            request.json["ip"],
            request.json["port"],
        )
        current_app.logger.debug(
            "%s: %s is issuing the following commands to %s:%s: %s",
            g.request_id,
            g.credentials.username,
            request.json["ip"],
            request.json["port"],
            request.json["commands"],
        )
        return f(*args, **kwargs)

    return wrapper
