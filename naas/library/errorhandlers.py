#!/usr/bin/env python3
# -*- coding: UTF-8 -*-


from naas import __version__


class DuplicateRequestID(Exception):
    pass


def api_error_generator():
    """
    API error dict generator for Flask-restful
    Some are just standard from werkzeug.exceptions, others are custom defined above.
    :return:
    """

    api_errors = {
        "BadRequest": {"status": 400, "error": "Invalid syntax in request"},
        "DuplicateRequestID": {"status": 400, "error": "Please provide a unique X-Request-ID"},
        "Unauthorized": {"status": 401, "error": "Please provide a valid Username/Password"},
        "Forbidden": {"status": 403, "error": "You are not currently allowed to access this resource"},
        "UnprocessableEntity": {
            "status": 422,
            "error": "Invalid type of data in request payload, please see documentation",
        },
        "InternalServerError": {
            "status": 500,
            "error": (
                "The server encountered an internal error and was unable to complete your request."
                "  Either the server is overloaded or there is an error in the application."
            ),
        },
    }

    # Error handling boilerplate to help make our common response payload
    error_boilerplate = {"app": "naas", "version": __version__}
    for err in api_errors:
        api_errors[err].update(error_boilerplate)

    return api_errors
