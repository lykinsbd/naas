# API Resource for wrapping netmiko's send_config() function

from flask import current_app, g, request
from flask_restful import Resource
from spectree import Response

from naas import __base_response__
from naas.config import JOB_TTL_FAILED, JOB_TTL_SUCCESS
from naas.library.audit import emit_audit_event
from naas.library.auth import device_lockout, job_locker
from naas.library.decorators import valid_post
from naas.library.errorhandlers import LockedOut
from naas.library.netmiko_lib import netmiko_send_config
from naas.models import JobResponse, SendConfigRequest
from naas.spec import spec


class SendConfig(Resource):
    @staticmethod
    def get():
        return __base_response__

    @valid_post
    @spec.validate(json=SendConfigRequest, resp=Response(HTTP_202=JobResponse))
    def post(self):
        """
        Will enqueue an attempt to use netmiko's send_config_set() method to run commands/put configuration on a device.

        Requires you submit the following in the payload:
            ip: str
            commands: Sequence[str]
        Optional:
            port: int - Default 22
            platform: str - Default cisco_ios
            enable: Optional[str] - Default the password provided for basic auth
            save_config: bool
            commit: bool

        Secured by Basic Auth, which is then passed to the network device.
        :return: A dict of the job ID, a 202 response code, and the job_id as the X-Request-ID header
        """
        validated: SendConfigRequest = request.context.json
        ip_str = str(validated.ip)

        if device_lockout(ip=ip_str):
            current_app.logger.error("%s: Device %s is locked out", g.request_id, ip_str)
            raise LockedOut

        # Log this request's details
        current_app.logger.info(
            "%s: %s is issuing %s command(s) to %s:%s",
            g.request_id,
            g.credentials.username,
            len(validated.config),
            ip_str,
            validated.port,
        )
        current_app.logger.debug(
            "%s: %s is issuing the following commands to %s:%s: %s",
            g.request_id,
            g.credentials.username,
            ip_str,
            validated.port,
            validated.config,
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
            netmiko_send_config,
            ip=ip_str,
            port=validated.port,
            device_type=validated.platform,
            credentials=g.credentials,
            commands=validated.config,
            save_config=validated.save_config,
            commit=validated.commit,
            delay_factor=validated.delay_factor,
            request_id=g.request_id,
            job_id=g.request_id,
            result_ttl=JOB_TTL_SUCCESS,
            failure_ttl=JOB_TTL_FAILED,
        )
        job_id = job.id
        current_app.logger.info("%s: Enqueued job for %s@%s:%s", job_id, g.credentials.username, ip_str, validated.port)

        # Generate the un/pw hash:
        user_hash = g.credentials.salted_hash()

        # Stash the job_id in redis, with the user/pass hash so that only that user can retrieve results
        job_locker(salted_creds=user_hash, job_id=job_id)

        # Emit audit event
        emit_audit_event(
            "job.submitted",
            ip=ip_str,
            platform=validated.platform,
            port=validated.port,
            command_count=len(validated.config),
            user_hash=user_hash,
            request_id=job_id,
        )

        # Return our payload containing job_id added to the base response, a 202 Accepted, and the X-Request-ID header
        response = JobResponse(job_id=job_id, message="Job enqueued").model_dump()
        response.update(__base_response__)
        return response, 202, {"X-Request-ID": job_id}
