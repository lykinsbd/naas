#!/usr/bin/env python3
# -*- coding: UTF-8 -*-


import logging

from flask import request
from functools import wraps
from naas.library import validation


logger = logging.getLogger(name="NAAS")


def valid_payload(f):
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
        v.is_config_set()
        v.is_command_set()
        v.custom_port()
        v.has_platform()
        logger.info(
            "%s is issuing %s command(s) to %s",
            request.authorization.username,
            len(request.json["commands"]),
            request.json["ip"],
        )
        logger.debug(
            "%s is issuing the following commands to %s: %s",
            request.authorization.username,
            request.json["ip"],
            request.json["commands"],
        )
        return f(*args, **kwargs)

    return wrapper


def valid_job_id(f):
    """
    Decorator function to check validity of a NAAS job_id
    :param f:
    :return:
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        v = validation.Validate()
        v.is_uuid()
        return f(*args, **kwargs)

    return wrapper
