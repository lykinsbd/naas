#!/usr/bin/env python3
# -*- coding: UTF-8 -*-


import ipaddress
from uuid import UUID

from flask import current_app, request
from werkzeug.exceptions import BadRequest, UnprocessableEntity

from naas.library.auth import tacacs_auth_lockout
from naas.library.errorhandlers import DuplicateRequestID, InvalidIP, LockedOut, NoAuth, NoJSON


class Validate:
    """
    This class contains many validation methods for ensuring we get correct/well formed requests.

    This class can be accessed directly or via a decorator in the `naas.library.decorators` module.

    It is not necessary (or possible) to use all validations on one request.
    """

    def __init__(self) -> None:
        """
        Initialize with some basic information hung on this object:
        self.headers for HTTP header information of this request
        self.method for the HTTP method of this request
        :return:
        """

        self.headers = {k.lower(): v for k, v in request.headers.items()}
        self.method = request.method

    @staticmethod
    def is_json() -> None:
        """
        Validate if the request is recognized as JSON
        :return:
        """
        if not request.json:
            current_app.logger.error("payload did not contain JSON")
            raise NoJSON

    @staticmethod
    def has_auth() -> None:
        """
        Ensure that the request has provided authorization headers (basic with username and password)
        :return:
        """
        if (
            not request.authorization
            or request.authorization.username is None
            or request.authorization.password is None
        ):
            current_app.logger.error("user did not pass authentication information")
            raise NoAuth

    @staticmethod
    def locked_out() -> None:
        """
        Validate if this user is locked out from accessing the API
        :return:
        """

        if tacacs_auth_lockout(username=request.authorization.username):
            current_app.logger.error(f"{request.authorization.username} is currently locked out.")
            raise LockedOut

    @staticmethod
    def has_port() -> None:
        """
        If "port" is in payload, don't do anything, otherwise set it to 22
        :return:
        """
        request.json.setdefault("port", 22)

    @staticmethod
    def is_ip_addr() -> None:
        """
        Validate that an IP address field is present in the request JSON and that it is a valid IPv4 address.
        :return:
        """
        ip = request.json.get("ip", None)
        if ip is None:
            current_app.logger.error("no 'ip' field found in payload")
            raise BadRequest
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            current_app.logger.error("'ip' field in payload did not contain a valid IPv4 Address")
            raise InvalidIP

    @staticmethod
    def is_uuid(uuid: str) -> None:
        """
        Validate that a provided string is a version 4 UUID
        :param uuid:
        :return:
        """
        try:
            _ = UUID(uuid, version=4)
        except ValueError:
            current_app.logger.error("invalid UUID found")
            raise BadRequest

    @staticmethod
    def is_duplicate_job(job_id: str) -> None:
        """
        Validate there isn't already a job by this ID
        :param job_id: str of a job_id to check
        :return:
        """

        if current_app.config["q"].fetch_job(job_id=job_id) is not None:
            raise DuplicateRequestID

    @staticmethod
    def save_config() -> None:
        """
        If "save_config" bool is in payload, don't do anything, otherwise set it to False
        :return:
        """
        request.json.setdefault("save_config", False)

        # If it _was_ set, but it ain't a bool, get outta here fool
        if not isinstance(request.json["save_config"], bool):
            current_app.logger.error("save_config must be a Boolean")
            raise UnprocessableEntity

    @staticmethod
    def commit() -> None:
        """
        If "commit" bool is in payload, don't do anything, otherwise set it to False
        :return:
        """
        request.json.setdefault("commit", False)

        # If it _was_ set, but it ain't a bool, get outta here fool
        if not isinstance(request.json["commit"], bool):
            current_app.logger.error("commit must be a Boolean")
            raise UnprocessableEntity

    @staticmethod
    def is_command_set() -> None:
        """
        Validate that the field `commands` exists in a request payload, and that it is a list.
        :return:
        """
        if not request.json.get("commands"):
            current_app.logger.error("'commands' field not found in payload")
            raise BadRequest
        if not isinstance(request.json["commands"], list):
            current_app.logger.error("'commands' not provided in a list")
            raise UnprocessableEntity

    @staticmethod
    def has_device_type() -> None:
        """
        Validate that the field `device_type` exists in a request payload (set it to `cisco_ios` by default)
        and that it is a string if it did already exist.
        :return:
        """
        if not request.json.get("device_type"):
            request.json["device_type"] = "cisco_ios"
        if not isinstance(request.json["device_type"], str):
            current_app.logger.error("'device_type' not provided as a string")
            raise UnprocessableEntity

    @staticmethod
    def has_delay_factor() -> None:
        """
        Validate that the field `delay_factor` exists in a request payload (set it to `1` by default)
        and that it is an int if it did already exist.
        :return:
        """
        if not request.json.get("delay_factor"):
            request.json["delay_factor"] = 1
        if not isinstance(request.json["delay_factor"], int):
            current_app.logger.error("'delay_factor not provided as an integer")
            raise UnprocessableEntity
