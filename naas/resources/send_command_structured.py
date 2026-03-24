# API Resource for structured send_command with TextFSM parsing

from flask import current_app, g, request
from flask_restful import Resource
from rq.exceptions import NoSuchJobError
from rq.job import Callback
from rq.job import Job as RQJob
from spectree import Response

from naas import __base_response__
from naas.config import JOB_TIMEOUT, JOB_TTL_FAILED, JOB_TTL_SUCCESS
from naas.library.audit import emit_audit_event
from naas.library.auth import device_lockout, job_locker, job_unlocker
from naas.library.callbacks import on_job_complete, on_job_failure
from naas.library.context import get_queue_for_context
from naas.library.decorators import valid_post
from naas.library.dedup import get_duplicate_job_id, register_dedup_key
from naas.library.errorhandlers import LockedOut
from naas.library.idempotency import get_idempotent_job_id, store_idempotency_key
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

        q = get_queue_for_context(validated.context, current_app.config["redis"])

        # Check idempotency key if provided
        idempotency_key = request.headers.get("X-Idempotency-Key")
        if idempotency_key:
            existing_job_id = get_idempotent_job_id(idempotency_key, current_app.config["redis"])
            if existing_job_id:
                try:
                    existing_job = RQJob.fetch(existing_job_id, connection=current_app.config["redis"])
                    response = JobResponse(
                        job_id=existing_job_id,
                        message="Job enqueued",
                        queue_position=0,
                        enqueued_at=existing_job.enqueued_at.isoformat() if existing_job.enqueued_at else "",
                        timeout=JOB_TIMEOUT,
                        idempotent=True,
                    ).model_dump()
                    response.update(__base_response__)
                    return response, 202, {"X-Request-ID": existing_job_id}
                except NoSuchJobError:
                    pass

        # Check for duplicate in-flight job
        _commands = validated.commands
        duplicate_job_id = get_duplicate_job_id(
            ip_str, validated.platform, list(_commands), g.credentials.username, current_app.config["redis"]
        )
        if duplicate_job_id:
            try:
                dup_job = RQJob.fetch(duplicate_job_id, connection=current_app.config["redis"])
                # Only return dedup if current user owns the job
                _user_hash = g.credentials.salted_hash()
                if job_unlocker(salted_creds=_user_hash, job_id=duplicate_job_id):
                    response = JobResponse(
                        job_id=duplicate_job_id,
                        message="Job enqueued",
                        queue_position=0,
                        enqueued_at=dup_job.enqueued_at.isoformat() if dup_job.enqueued_at else "",
                        timeout=JOB_TIMEOUT,
                        deduplicated=True,
                    ).model_dump()
                    response.update(__base_response__)
                    return response, 202, {"X-Request-ID": duplicate_job_id}
            except NoSuchJobError:
                pass

        job = q.enqueue(
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
            on_success=Callback(on_job_complete),
            on_failure=Callback(on_job_failure),
        )
        job_id = job.id
        current_app.logger.info(
            "%s: Enqueued structured job for %s@%s:%s", job_id, g.credentials.username, ip_str, validated.port
        )

        user_hash = g.credentials.salted_hash()
        job_locker(salted_creds=user_hash, job=job)

        if idempotency_key:
            store_idempotency_key(idempotency_key, job_id, current_app.config["redis"])

        dedup_redis_key = register_dedup_key(
            ip_str, validated.platform, list(_commands), g.credentials.username, job_id, current_app.config["redis"]
        )
        if validated.tags or dedup_redis_key:
            if dedup_redis_key:
                job.meta["dedup_key"] = dedup_redis_key
            if validated.tags:
                job.meta["tags"] = validated.tags
            job.save_meta()

        emit_audit_event(
            "job.submitted",
            ip=ip_str,
            platform=validated.platform,
            port=validated.port,
            command_count=len(validated.commands),
            user_hash=user_hash,
            request_id=job_id,
        )

        queue_position = len(q.job_ids)
        response = JobResponse(
            job_id=job_id,
            message="Job enqueued",
            queue_position=queue_position,
            enqueued_at=job.enqueued_at.isoformat(),
            timeout=JOB_TIMEOUT,
            idempotent=False,
            deduplicated=False,
        ).model_dump()
        response.update(__base_response__)
        return response, 202, {"X-Request-ID": job_id}
