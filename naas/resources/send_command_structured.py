# API Resource for structured send_command with TextFSM parsing

from flask import current_app, g, request
from flask_restful import Resource
from spectree import Response

from naas import __base_response__
from naas.config import JOB_TIMEOUT, JOB_TTL_FAILED, JOB_TTL_SUCCESS
from naas.library.audit import emit_audit_event
from naas.library.auth import device_lockout, job_locker
from naas.library.decorators import valid_post
from naas.library.errorhandlers import LockedOut
from naas.library.netmiko_lib import netmiko_send_command_structured
from naas.models import JobResponse, SendCommandStructuredRequest
from naas.spec import spec


class SendCommandStructured(Resource):
    @staticmethod
    def get():
        return __base_response__

    @valid_post
    @spec.validate(json=SendCommandStructuredRequest, resp=Response(HTTP_202=JobResponse))
    def post(self):
        """
        Enqueue a send_command job with TextFSM parsing for structured output.

        Returns parsed list[dict] per command (or raw string if no template found).
        Uses ntc-templates by default, or custom template if provided.

        Requires:
            ip: str
            commands: Sequence[str]
        Optional:
            port: int - Default 22
            platform: str - Default cisco_ios (use "autodetect" for SSHDetect)
            read_timeout: float - Default 30.0 seconds
            textfsm_template: str - Custom TextFSM template (uses ntc-templates if omitted)

        Secured by Basic Auth, which is then passed to the network device.
        :return: A dict of the job ID, a 202 response code, and the job_id as the X-Request-ID header
        """
        validated: SendCommandStructuredRequest = request.context.json
        ip_str = validated.host

        if device_lockout(ip=ip_str, redis=current_app.config["redis"]):
            current_app.logger.error("%s: Device %s is locked out", g.request_id, ip_str)
            raise LockedOut

        current_app.logger.info(
            "%s: %s is issuing %s structured command(s) to %s:%s",
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

        job = current_app.config["q"].enqueue(
            netmiko_send_command_structured,
            ip=ip_str,
            port=validated.port,
            device_type=validated.platform,
            credentials=g.credentials,
            commands=validated.commands,
            read_timeout=validated.read_timeout,
            textfsm_template=validated.textfsm_template,
            ttp_template=validated.ttp_template,
            request_id=g.request_id,
            job_id=g.request_id,
            job_timeout=JOB_TIMEOUT,
            result_ttl=JOB_TTL_SUCCESS,
            failure_ttl=JOB_TTL_FAILED,
        )
        job_id = job.id
        current_app.logger.info(
            "%s: Enqueued structured job for %s@%s:%s", job_id, g.credentials.username, ip_str, validated.port
        )

        user_hash = g.credentials.salted_hash()
        job_locker(salted_creds=user_hash, job=job)

        emit_audit_event(
            "job.submitted",
            ip=ip_str,
            platform=validated.platform,
            port=validated.port,
            command_count=len(validated.commands),
            user_hash=user_hash,
            request_id=job_id,
        )

        queue_position = len(current_app.config["q"].job_ids)
        response = JobResponse(
            job_id=job_id,
            message="Job enqueued",
            queue_position=queue_position,
            enqueued_at=job.enqueued_at.isoformat(),
            timeout=JOB_TIMEOUT,
        ).model_dump()
        response.update(__base_response__)
        return response, 202, {"X-Request-ID": job_id}
