# API Resource for wrapping netmiko's send_command() function

from flask import current_app, g, request
from flask_restful import Resource
from spectree import Response

from naas import __base_response__
from naas.library.auth import job_locker
from naas.library.decorators import valid_post
from naas.library.netmiko_lib import netmiko_send_command
from naas.models import JobResponse, SendCommandRequest
from naas.spec import spec


class SendCommand(Resource):
    @staticmethod
    def get():
        return __base_response__

    @valid_post
    @spec.validate(json=SendCommandRequest, resp=Response(HTTP_202=JobResponse))
    def post(self):
        """
        Will enqueue an attempt to run commands on a device.

        Requires you submit the following in the payload:
            ip: str
            commands: Sequence[str]
        Optional:
            port: int - Default 22
            platform: str - Default cisco_ios
            enable: Optional[str] - Default the password provided for basic auth

        Secured by Basic Auth, which is then passed to the network device.
        :return: A dict of the job ID, a 202 response code, and the job_id as the X-Request-ID header
        """
        validated: SendCommandRequest = request.context.json
        ip_str = str(validated.ip)

        # Log this request's details
        current_app.logger.info(
            "%s: %s is issuing %s command(s) to %s:%s",
            g.request_id,
            g.credentials.username,
            len(validated.commands),
            ip_str,
            validated.port,
        )
        current_app.logger.debug(
            "%s: %s is issuing the following commands to %s:%s: %s",
            g.request_id,
            g.credentials.username,
            ip_str,
            validated.port,
            validated.commands,
        )

        # Enqueue your job, and return the job ID
        current_app.logger.debug(
            "%s: Enqueueing job for %s@%s:%s",
            g.request_id,
            g.credentials.username,
            ip_str,
            validated.port,
        )
        job = current_app.config["q"].enqueue(
            netmiko_send_command,
            ip=ip_str,
            port=validated.port,
            device_type=validated.platform,
            credentials=g.credentials,
            commands=validated.commands,
            delay_factor=validated.delay_factor,
            request_id=g.request_id,
            job_id=g.request_id,
            result_ttl=86460,
            failure_ttl=86460,
        )
        job_id = job.get_id()
        current_app.logger.info("%s: Enqueued job for %s@%s:%s", job_id, g.credentials.username, ip_str, validated.port)

        # Generate the un/pw hash:
        user_hash = g.credentials.salted_hash()

        # Stash the job_id in redis, with the user/pass hash so that only that user can retrieve results
        job_locker(salted_creds=user_hash, job_id=job_id)

        # Return our payload containing job_id, a 202 Accepted, and the X-Request-ID header
        response = JobResponse(job_id=job_id, message="Job enqueued").model_dump()
        response.update(__base_response__)
        return response, 202, {"X-Request-ID": job_id}
