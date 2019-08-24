# API Resource for wrapping netmiko's send_command() function

from flask_restful import Resource
from flask import current_app, g, request
from naas import __base_response__
from naas.library.auth import job_locker
from naas.library.decorators import valid_post
from naas.library.netmiko_lib import netmiko_send_command


class SendCommand(Resource):
    @staticmethod
    def get():
        return __base_response__

    @valid_post
    def post(self):
        """
        Will enqueue an attempt to run commands on a device.

        Requires you submit the following in the payload:
            ip: str
            commands: Sequence[str]
        Optional:
            port: int - Default 22
            device_type: str - Default cisco_ios
            enable: Optional[str] - Default the password provided for basic auth

        Secured by Basic Auth, which is then passed to the network device.
        :return: A dict of the job ID, a 202 response code, and the job_id as the X-Request-ID header
        """

        # Enqueue your job, and return the job ID
        current_app.logger.debug(
            "%s: Enqueueing job for %s@%s:%s",
            g.request_id,
            g.credentials.username,
            request.json["ip"],
            request.json["port"],
        )
        job = current_app.config["q"].enqueue(
            netmiko_send_command,
            ip=request.json["ip"],
            port=request.json["port"],
            device_type=request.json["device_type"],
            credentials=g.credentials,
            commands=request.json["commands"],
            job_id=g.request_id,
            result_ttl=86460,
            failure_ttl=86460,
        )
        job_id = job.get_id()
        current_app.logger.info(
            "%s: Enqueued job for %s@%s:%s", job_id, g.credentials.username, request.json["ip"], request.json["port"]
        )

        # Generate the un/pw hash:
        user_hash = g.credentials.salted_hash()

        # Stash the job_id in redis, with the user/pass hash so that only that user can retrieve results
        job_locker(salted_creds=user_hash, job_id=job_id)

        # Return our payload containing job_id, a 202 Accepted, and the X-Request-ID header
        response = {"job_id": job_id}
        response.update(__base_response__)
        return response, 202, {"X-Request-ID": job_id}
