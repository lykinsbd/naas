#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

from functools import wraps
from uuid import uuid4

from flask import g, request

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

        return f(*args, **kwargs)

    return wrapper
