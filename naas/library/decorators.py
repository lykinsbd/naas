#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

from functools import wraps
from uuid import uuid4

from flask import g, request
from werkzeug.exceptions import Forbidden, UnprocessableEntity

from naas.library import validation
from naas.library.audit import emit_audit_event
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
        if g.auth_method == "bearer":
            # JWT auth: device credentials come from request body
            body = request.json
            username = body.get("username")
            password = body.get("password")
            if not username or not password:
                raise UnprocessableEntity("username and password are required in request body when using API key auth")
            g.credentials = Credentials(
                username=username,
                password=password,
                enable=body.get("enable"),
            )
            # Context authorization: check JWT contexts claim
            context = body.get("context", "default")
            allowed = g.jwt_claims.get("contexts", [])
            if "*" not in allowed and context not in allowed:
                emit_audit_event(
                    "auth.context_denied",
                    identity=g.jwt_claims["sub"],
                    context=context,
                    allowed_contexts=",".join(allowed),
                )
                raise Forbidden(f"API key not authorized for context '{context}'")
        else:
            # Basic auth: device credentials from Authorization header
            g.credentials = Credentials(
                username=request.authorization.username,
                password=request.authorization.password,
                enable=request.json.get("enable", None),
            )

        return f(*args, **kwargs)

    return wrapper
