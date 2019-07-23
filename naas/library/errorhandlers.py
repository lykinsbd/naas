#!/usr/bin/env python3
# -*- coding: UTF-8 -*-


from naas import __version__


class SshAuthentication(Exception):
    pass


class SshError(Exception):
    pass


class SshTimeout(Exception):
    pass


def api_error_generator():
    """
    API error dict generator for Flask-restful
    Some are just standard from werkzeug.exceptions, others are custom defined above.
    :return:
    """

    api_errors = {
        "BadRequest": {"status": 400, "error": "Invalid syntax in request"},
        "UnprocessableEntity": {"status": 422, "error": "Please provide commands in List form"},
        "InternalServerError": {
            "status": 500,
            "error": (
                "The server encountered an internal error and was unable to complete your request."
                "  Either the server is overloaded or there is an error in the application."
            ),
        },
        "SshError": {"status": 502, "error": "SSH - Unknown Error connecting to device"},
        "SshAuthentication": {"status": 502, "error": "SSH - Unable to authenticate to device"},
        "SshTimeout": {"status": 504, "error": "SSH - Connection timed out to device"},
    }

    # Error handling boilerplate to help make a valid payload
    error_boilerplate = {"success": False, "output": None, "app": "naas", "version": __version__}
    for err in api_errors:
        api_errors[err].update(error_boilerplate)

    return api_errors
