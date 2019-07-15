# API Resources

from collections import OrderedDict
from flask_restful import Resource
from flask import request
from naas import __version__
from naas.library.decorators import valid_payload
from naas.library.netmiko_lib import NetmikoWrapper
from naas.library.errorhandlers import SshTimeout, SshAuthentication, SshError


class Commands(Resource):

    @staticmethod
    def get():
        return {"hello": "world", "app": "naas", "version": __version__}

    @valid_payload
    def post(self):
        """
        Handle posting of config_sets to netmiko
        :return:
        """

        # Execute your commands and return the output (or error)
        n = NetmikoWrapper(
            ip=request.json["ip"],
            port=request.json["port"],
            platform=request.json["platform"],
            username=request.json["username"],
            password=request.json["password"],
            enable=request.json.get("enable", request.json["password"]),
            config_set=request.json["config_set"],
            commands=request.json["commands"],
        )
        output, error = n.send_commands()

        response_payload = OrderedDict(
            {"success": True, "output": output, "error": None, "app": "naas", "version": __version__}
        )

        # If we succeeded, give back the output.
        if not error:
            return response_payload
        # If we failed in some way to reach the device, give the error.
        else:
            # Set success to false
            response_payload["success"] = False

            if "timed-out" in error:
                raise SshTimeout
            elif "Authentication" in error:
                raise SshAuthentication
            else:
                raise SshError
