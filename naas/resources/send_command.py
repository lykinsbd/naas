# API Resources

from flask_restful import Resource
from flask import current_app, request
from logging import getLogger
from naas import __version__
from naas.library.auth import job_locker
from naas.library.decorators import valid_payload
from naas.library.netmiko_lib import netmiko_send_command
from werkzeug.exceptions import Unauthorized


logger = getLogger("NAAS")


class SendCommand(Resource):
    @staticmethod
    def get():
        return {"app": "naas", "version": __version__}

    @valid_payload
    def post(self):
        """
        Will enqueue an attempt to run commands on a device.

        Requires you submit the following in the payload:
            ip: str
            port: int
            platform: str
            enable: Optional[str]
            config_set: bool
            commands: Sequence[str]
        Secured by Basic Auth, which is then passed to the network device.
        :return: A dict of the job ID and 202 response code.
        """

        # Grab creds off the basic_auth header
        auth = request.authorization
        if auth.username is None:
            raise Unauthorized

        # Enqueue your job, and return the job ID
        logger.debug("Enqueueing job for %s@%s:%s", auth.username, request.json["ip"], request.json["port"])
        q = current_app.config["q"]
        job = q.enqueue(
            netmiko_send_command,
            ip=request.json["ip"],
            port=request.json["port"],
            platform=request.json["platform"],
            username=auth.username,
            password=auth.password,
            enable=request.json.get("enable", auth.password),
            commands=request.json["commands"],
        )
        job_id = job.get_id()
        logger.debug("Enqueued job (%s) for %s@%s:%s", job_id, auth.username, request.json["ip"], request.json["port"])

        # Stash the job_id in redis, with the user/pass hash so that only that user can retrieve results
        job_locker(username=auth.username, password=auth.password, job_id=job_id)

        return {"job_id": job_id, "app": "naas", "version": __version__}, 202
