# API Resource for wrapping netmiko's send_config() function

from flask import current_app, g, request
from flask_restful import Resource
from rq.exceptions import NoSuchJobError
from rq.job import Callback
from rq.job import Job as RQJob
from spectree import Response

from naas import __base_response__
from naas.config import JOB_TIMEOUT, JOB_TTL_FAILED, JOB_TTL_SUCCESS
from naas.library.audit import emit_audit_event
from naas.library.auth import device_lockout, job_locker
from naas.library.callbacks import on_job_complete, on_job_failure
from naas.library.context import get_queue_for_context
from naas.library.decorators import valid_post
from naas.library.dedup import get_duplicate_job_id, register_dedup_key
from naas.library.errorhandlers import LockedOut
from naas.library.idempotency import get_idempotent_job_id, store_idempotency_key
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
        ip_str = validated.host

        if device_lockout(ip=ip_str, redis=current_app.config["redis"]):
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

        # Check idempotency key if provided
        idempotency_key = request.headers.get("X-Idempotency-Key")
        if idempotency_key:
            existing_job_id = get_idempotent_job_id(idempotency_key, current_app.config["redis"])
            if existing_job_id:
                try:
                    existing_job = RQJob.fetch(existing_job_id, connection=current_app.config["redis"])
                    queue_position = 0
                    response = JobResponse(
                        job_id=existing_job_id,
                        message="Job enqueued",
                        queue_position=queue_position,
                        enqueued_at=existing_job.enqueued_at.isoformat() if existing_job.enqueued_at else "",
                        timeout=JOB_TIMEOUT,
                        idempotent=True,
                    ).model_dump()
                    response.update(__base_response__)
                    return response, 202, {"X-Request-ID": existing_job_id}
                except NoSuchJobError:
                    pass  # Key expired or job gone, proceed with new enqueue

        # Validate context and get queue (raises 400/503 before dedup check)
        q = get_queue_for_context(validated.context, current_app.config["redis"])

        # Check for duplicate in-flight job (server-side dedup)
        _commands = validated.commands or validated.config or []
        duplicate_job_id = get_duplicate_job_id(
            ip_str, validated.platform, list(_commands), g.credentials.username, current_app.config["redis"]
        )
        if duplicate_job_id:
            try:
                dup_job = RQJob.fetch(duplicate_job_id, connection=current_app.config["redis"])
                queue_position = 0
                response = JobResponse(
                    job_id=duplicate_job_id,
                    message="Job enqueued",
                    queue_position=queue_position,
                    enqueued_at=dup_job.enqueued_at.isoformat() if dup_job.enqueued_at else "",
                    timeout=JOB_TIMEOUT,
                    deduplicated=True,
                ).model_dump()
                response.update(__base_response__)
                return response, 202, {"X-Request-ID": duplicate_job_id}
            except NoSuchJobError:
                pass  # Job gone, proceed with new enqueue

        # Enqueue your job, and return the job ID
        current_app.logger.debug(
            "%s: Enqueueing job for %s@%s:%s",
            g.request_id,
            g.credentials.username,
            ip_str,
            validated.port,
        )
        job = q.enqueue(
            netmiko_send_config,
            ip=ip_str,
            port=validated.port,
            device_type=validated.platform,
            credentials=g.credentials,
            commands=validated.config,
            save_config=validated.save_config,
            commit=validated.commit,
            read_timeout=validated.read_timeout,
            request_id=g.request_id,
            job_id=g.request_id,
            job_timeout=JOB_TIMEOUT,
            result_ttl=JOB_TTL_SUCCESS,
            failure_ttl=JOB_TTL_FAILED,
            on_success=Callback(on_job_complete),
            on_failure=Callback(on_job_failure),
        )
        job_id = job.id
        current_app.logger.info("%s: Enqueued job for %s@%s:%s", job_id, g.credentials.username, ip_str, validated.port)

        # Generate the un/pw hash:
        user_hash = g.credentials.salted_hash()

        # Stash the job_id in redis, with the user/pass hash so that only that user can retrieve results
        job_locker(salted_creds=user_hash, job=job)

        # Register dedup key and store in job meta for cleanup
        dedup_redis_key = register_dedup_key(
            ip_str, validated.platform, list(_commands), g.credentials.username, job_id, current_app.config["redis"]
        )
        if dedup_redis_key:
            job.meta["dedup_key"] = dedup_redis_key

        # Store idempotency key if provided
        if idempotency_key:
            store_idempotency_key(idempotency_key, job_id, current_app.config["redis"])

        # Store tags in job metadata if provided
        if validated.tags:
            job.meta["tags"] = validated.tags
        if job.meta:
            job.save_meta()

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
        queue_position = len(q.job_ids)
        response = JobResponse(
            job_id=job_id,
            message="Job enqueued",
            queue_position=queue_position,
            enqueued_at=job.enqueued_at.isoformat(),
            timeout=JOB_TIMEOUT,
            idempotent=False,
        ).model_dump()
        response.update(__base_response__)
        return response, 202, {"X-Request-ID": job_id}
