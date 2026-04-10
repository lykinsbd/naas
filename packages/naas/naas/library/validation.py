#!/usr/bin/env python3
# -*- coding: UTF-8 -*-


from uuid import UUID

import jwt
from flask import current_app, g, request
from werkzeug.exceptions import BadRequest

from naas.library.api_keys import validate_api_key
from naas.library.audit import emit_audit_event
from naas.library.auth import tacacs_auth_lockout
from naas.library.errorhandlers import DuplicateRequestID, LockedOut, NoAuth, NoJSON


class Validate:
    """
    This class contains validation methods for ensuring we get correct/well formed requests.

    This class can be accessed directly or via a decorator in the `naas.library.decorators` module.
    """

    def __init__(self) -> None:
        self.headers = {k.lower(): v for k, v in request.headers.items()}
        self.method = request.method

    @staticmethod
    def is_json() -> None:
        """Validate if the request is recognized as JSON."""
        if not request.json:
            current_app.logger.error("payload did not contain JSON")
            raise NoJSON

    @staticmethod
    def has_auth() -> None:
        """Ensure the request has valid authentication (Basic or Bearer JWT).

        Sets ``g.auth_method`` to ``"basic"`` or ``"bearer"`` and, for Bearer,
        stores decoded claims on ``g.jwt_claims``.
        """
        auth_header = request.headers.get("Authorization", "")

        # Bearer JWT path
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ")
            try:
                g.jwt_claims = validate_api_key(token)
                g.auth_method = "bearer"
                emit_audit_event("auth.success", method="bearer", identity=g.jwt_claims["sub"])
                return
            except jwt.InvalidTokenError as exc:
                current_app.logger.error("Invalid API key: %s", exc)
                emit_audit_event("auth.failure", method="bearer", reason=str(exc))
                raise NoAuth

        # Basic auth path (existing behaviour)
        if (
            not request.authorization
            or request.authorization.username is None
            or request.authorization.password is None
        ):
            current_app.logger.error("user did not pass authentication information")
            emit_audit_event("auth.failure", method="none", reason="missing credentials")
            raise NoAuth
        g.auth_method = "basic"
        emit_audit_event("auth.success", method="basic", identity=request.authorization.username)

    @staticmethod
    def locked_out() -> None:
        """Validate if this user is locked out from accessing the API."""
        if getattr(g, "auth_method", None) == "bearer":
            return  # JWT-authenticated users are not subject to TACACS lockout
        if request.authorization and request.authorization.username:
            if tacacs_auth_lockout(username=request.authorization.username, redis=current_app.config["redis"]):
                current_app.logger.error(f"{request.authorization.username} is currently locked out.")
                raise LockedOut

    @staticmethod
    def is_uuid(uuid: str) -> None:
        """Validate that a provided string is a version 4 UUID."""
        try:
            _ = UUID(uuid, version=4)
        except ValueError:
            current_app.logger.error("invalid UUID found")
            raise BadRequest

    @staticmethod
    def is_duplicate_job(job_id: str) -> None:
        """Validate there isn't already a job by this ID."""
        if current_app.config["q"].fetch_job(job_id=job_id) is not None:
            raise DuplicateRequestID
