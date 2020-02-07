#!/usr/bin/env python3
# -*- coding: UTF-8 -*-


from naas import __base_response__
from werkzeug.exceptions import BadRequest, Forbidden, Unauthorized, UnprocessableEntity


class DuplicateRequestID(BadRequest):
    pass


class InvalidIP(UnprocessableEntity):
    pass


class LockedOut(Forbidden):
    pass


class NoAuth(Unauthorized):
    pass


class NoJSON(BadRequest):
    pass


def api_error_generator():
    """
    API error dict generator for Flask-restful
    Some are just standard from werkzeug.exceptions, others are custom defined above.
    :return:
    """

    api_errors = {
        "BadRequest": {"status": 400, "error": "Invalid syntax in request"},
        "NoJSON": {"status": 400, "error": "Payload must be JSON"},
        "DuplicateRequestID": {"status": 400, "error": "Please provide a unique X-Request-ID"},
        "Unauthorized": {"status": 401, "error": "Please provide a valid Username/Password"},
        "NoAuth": {"status": 401, "error": "You must authenticate with HTTP Basic authentication to use this resource"},
        "Forbidden": {"status": 403, "error": "You are not currently allowed to access this resource"},
        "LockedOut": {
            "status": 403,
            "error": "You are currently locked out for excessive login failures, please try again later",
        },
        "UnprocessableEntity": {
            "status": 422,
            "error": "Invalid type of data in request payload, please see documentation",
        },
        "InvalidIP": {"status": 422, "error": "Invalid IPv4 address in 'ip' field of payload"},
        "InternalServerError": {
            "status": 500,
            "error": (
                "The server encountered an internal error and was unable to complete your request."
                "  Either the server is overloaded or there is an error in the application."
            ),
        },
    }

    # Error handling boilerplate to help make our common response payload
    for err in api_errors:
        api_errors[err].update(__base_response__)

    return api_errors
