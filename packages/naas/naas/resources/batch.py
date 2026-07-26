"""API Resources for batch/bulk operations.

POST /v2/send-command/batch — fan-out commands to N devices
POST /v2/send-config/batch — fan-out config to N devices
GET /v2/batches/{batch_id} — aggregate batch status
"""

from __future__ import annotations

from flask import current_app, g, request
from flask_restful import Resource
from rq.job import Callback
from rq.job import Job as RQJob
from spectree import Response
from werkzeug.exceptions import Forbidden, NotFound, TooManyRequests, UnprocessableEntity

from naas.config import (
    BATCH_MAX_COMMANDS,
    BATCH_MAX_DEVICES,
    JOB_TIMEOUT,
    JOB_TTL_FAILED,
    JOB_TTL_SUCCESS,
    MAX_QUEUE_DEPTH,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_PER_CALLER,
    RATE_LIMIT_WINDOW,
)
from naas.library.audit import emit_audit_event
from naas.library.auth import job_locker, require_role
from naas.library.batch import generate_batch_id, get_batch, store_batch, validate_batch_ownership
from naas.library.callbacks import on_job_complete, on_job_failure
from naas.library.context import get_queue_for_context
from naas.library.decorators import valid_post
from naas.library.netmiko_lib import netmiko_send_command, netmiko_send_config
from naas.library.otel import inject_traceparent
from naas.library.rate_limit import _get_caller_id, _is_exempt
from naas.models import (
    BatchSendCommandRequest,
    BatchSendConfigRequest,
    BatchStatusResponse,
    BatchSubmitResponse,
)
from naas.spec import spec


def _check_batch_rate_limit(device_count: int) -> None:
    """Check rate limit for batch submission (cost = number of devices).

    Raises TooManyRequests if insufficient quota.
    """
    if not RATE_LIMIT_ENABLED or _is_exempt():
        return

    redis = current_app.config["redis"]
    caller_id = _get_caller_id()
    redis_key = f"naas:ratelimit:{caller_id}"

    # Check current usage without consuming
    now = __import__("time").time()
    redis.zremrangebyscore(redis_key, 0, now - RATE_LIMIT_WINDOW)
    current_count: int = redis.zcard(redis_key)  # type: ignore[assignment]
    remaining = max(0, RATE_LIMIT_PER_CALLER - current_count)

    if device_count > remaining:
        g.rate_limit_limit = RATE_LIMIT_PER_CALLER
        g.rate_limit_remaining = remaining
        g.rate_limit_reset = int(now + RATE_LIMIT_WINDOW)
        raise TooManyRequests(
            f"Rate limit insufficient: batch requires {device_count} units but only {remaining} remaining in window"
        )

    # Consume N units
    from uuid import uuid4

    pipe = redis.pipeline()
    for _ in range(device_count):
        pipe.zadd(redis_key, {str(uuid4()): now})
    pipe.expire(redis_key, RATE_LIMIT_WINDOW)
    pipe.execute()

    g.rate_limit_limit = RATE_LIMIT_PER_CALLER
    g.rate_limit_remaining = max(0, remaining - device_count)
    g.rate_limit_reset = int(now + RATE_LIMIT_WINDOW)


def _check_batch_queue_depth(contexts: list[str]) -> None:
    """Best-effort check that queues can accommodate the batch.

    Groups devices by context and checks each queue. Raises QueueFull
    if any context would exceed MAX_QUEUE_DEPTH.
    """
    if MAX_QUEUE_DEPTH <= 0:
        return

    from collections import Counter

    from rq import Queue

    redis = current_app.config["redis"]
    context_counts = Counter(contexts)

    for ctx, count in context_counts.items():
        queue_name = f"naas-{ctx}"
        q = Queue(queue_name, connection=redis)
        if len(q) + count > MAX_QUEUE_DEPTH:
            from naas.library.errorhandlers import QueueFull

            raise QueueFull


def _enqueue_batch_jobs(
    devices: list,
    commands: list[str],
    batch_id: str,
    worker_fn,
    default_username: str | None,
    default_password: str | None,
    default_enable: str | None,
    default_port: int,
    default_context: str,
    extra_kwargs: dict | None = None,
) -> list[dict[str, str]]:
    """Fan-out: enqueue one job per device, return list of {job_id, host}.

    Args:
        devices: List of BatchDeviceEntry models.
        commands: Commands to execute.
        batch_id: Batch correlation ID.
        worker_fn: The netmiko worker function to enqueue.
        default_*: Batch-level defaults for credentials/port/context.
        extra_kwargs: Additional kwargs for the worker function (e.g. commit, save_config).

    Returns:
        List of {"job_id": str, "host": str} dicts.
    """
    redis = current_app.config["redis"]
    credentials = g.credentials
    jobs_created: list[dict[str, str]] = []

    for device in devices:
        # Resolve per-device overrides
        host = device.host
        platform = device.platform
        port = device.port or default_port
        username = device.username or default_username or credentials.username
        password = device.password or default_password or credentials.password
        enable = device.enable or default_enable or credentials.enable
        context = device.context or default_context

        # Get queue for this device's context
        q = get_queue_for_context(context, redis)

        # Build worker kwargs
        kwargs = {
            "ip": host,
            "port": port,
            "device_type": platform,
            "commands": commands,
            "credentials": credentials.__class__(username=username, password=password, enable=enable),
            "request_id": None,  # Will be set below
        }
        if extra_kwargs:
            kwargs.update(extra_kwargs)

        # Inject OTel traceparent if available
        inject_traceparent(kwargs)

        # Enqueue the job
        job = q.enqueue(
            worker_fn,
            kwargs=kwargs,
            job_timeout=JOB_TIMEOUT,
            result_ttl=JOB_TTL_SUCCESS,
            failure_ttl=JOB_TTL_FAILED,
            on_success=Callback(on_job_complete),
            on_failure=Callback(on_job_failure),
        )

        # Set request_id to job.id for tracing
        kwargs["request_id"] = job.id

        # Store batch_id in job meta for correlation
        job.meta["batch_id"] = batch_id
        job.meta["host"] = host
        job.save_meta()

        # Lock the job to the caller
        job_locker(credentials.salted_hash(), job)

        jobs_created.append({"job_id": job.id, "host": host})

    return jobs_created


class BatchSendCommand(Resource):
    """POST /v2/send-command/batch — submit commands to multiple devices."""

    @valid_post
    @require_role("operator")
    @spec.validate(json=BatchSendCommandRequest, resp=Response(HTTP_202=BatchSubmitResponse))
    def post(self):
        """Submit a batch of send-command jobs to multiple devices."""
        data = BatchSendCommandRequest.model_validate(request.json)

        # Validate limits
        if len(data.devices) > BATCH_MAX_DEVICES:
            raise UnprocessableEntity(
                f"Batch exceeds maximum of {BATCH_MAX_DEVICES} devices ({len(data.devices)} provided)"
            )
        if len(data.commands) > BATCH_MAX_COMMANDS:
            raise UnprocessableEntity(
                f"Batch exceeds maximum of {BATCH_MAX_COMMANDS} commands ({len(data.commands)} provided)"
            )

        # Rate limit check (cost = number of devices)
        _check_batch_rate_limit(len(data.devices))

        # Queue depth check (best-effort, per context)
        contexts = [d.context or data.context for d in data.devices]
        _check_batch_queue_depth(contexts)

        # Generate batch ID and fan-out
        batch_id = generate_batch_id()
        redis = current_app.config["redis"]

        jobs = _enqueue_batch_jobs(
            devices=data.devices,
            commands=data.commands,
            batch_id=batch_id,
            worker_fn=netmiko_send_command,
            default_username=data.username,
            default_password=data.password,
            default_enable=data.enable,
            default_port=data.port,
            default_context=data.context,
            extra_kwargs={"expect_string": data.expect_string} if data.expect_string else None,
        )

        # Store batch metadata
        store_batch(redis, batch_id, jobs, g.credentials.salted_hash())

        emit_audit_event(
            "batch.submitted",
            batch_id=batch_id,
            device_count=len(jobs),
            operation="send_command",
        )

        return {"batch_id": batch_id, "job_ids": [j["job_id"] for j in jobs], "total": len(jobs)}, 202


class BatchSendConfig(Resource):
    """POST /v2/send-config/batch — submit config to multiple devices."""

    @valid_post
    @require_role("operator")
    @spec.validate(json=BatchSendConfigRequest, resp=Response(HTTP_202=BatchSubmitResponse))
    def post(self):
        """Submit a batch of send-config jobs to multiple devices."""
        data = BatchSendConfigRequest.model_validate(request.json)

        # Validate limits
        if len(data.devices) > BATCH_MAX_DEVICES:
            raise UnprocessableEntity(
                f"Batch exceeds maximum of {BATCH_MAX_DEVICES} devices ({len(data.devices)} provided)"
            )
        if len(data.commands) > BATCH_MAX_COMMANDS:
            raise UnprocessableEntity(
                f"Batch exceeds maximum of {BATCH_MAX_COMMANDS} commands ({len(data.commands)} provided)"
            )

        # Rate limit check (cost = number of devices)
        _check_batch_rate_limit(len(data.devices))

        # Queue depth check (best-effort, per context)
        contexts = [d.context or data.context for d in data.devices]
        _check_batch_queue_depth(contexts)

        # Generate batch ID and fan-out
        batch_id = generate_batch_id()
        redis = current_app.config["redis"]

        extra_kwargs: dict = {}
        if data.commit:
            extra_kwargs["commit"] = True
        if data.save_config:
            extra_kwargs["save_config"] = True

        jobs = _enqueue_batch_jobs(
            devices=data.devices,
            commands=data.commands,
            batch_id=batch_id,
            worker_fn=netmiko_send_config,
            default_username=data.username,
            default_password=data.password,
            default_enable=data.enable,
            default_port=data.port,
            default_context=data.context,
            extra_kwargs=extra_kwargs or None,
        )

        # Store batch metadata
        store_batch(redis, batch_id, jobs, g.credentials.salted_hash())

        emit_audit_event(
            "batch.submitted",
            batch_id=batch_id,
            device_count=len(jobs),
            operation="send_config",
        )

        return {"batch_id": batch_id, "job_ids": [j["job_id"] for j in jobs], "total": len(jobs)}, 202


class BatchStatus(Resource):
    """GET /v2/batches/{batch_id} — get aggregate batch status."""

    @require_role("viewer")
    @spec.validate(resp=Response(HTTP_200=BatchStatusResponse))
    def get(self, batch_id: str):
        """Get the status of a batch and all its constituent jobs."""
        from naas.library.auth import Credentials

        redis = current_app.config["redis"]

        # Fetch batch metadata
        batch_data = get_batch(redis, batch_id)
        if batch_data is None:
            raise NotFound(f"Batch '{batch_id}' not found or has expired")

        # Build credentials for ownership check
        auth = request.authorization
        if auth and auth.username and auth.password:
            creds = Credentials(username=auth.username, password=auth.password)
            salted = creds.salted_hash()
        elif hasattr(g, "jwt_claims"):
            # JWT auth: use the sub claim as a pseudo-hash for ownership
            salted = g.jwt_claims.get("sub", "")
        else:
            raise Forbidden("Cannot verify batch ownership")

        # Validate ownership
        if not validate_batch_ownership(batch_data, salted):
            raise Forbidden("You do not have access to this batch")

        # Query status of each job
        jobs_status = []
        completed = 0
        pending = 0
        failed = 0

        for job_entry in batch_data["jobs"]:
            job_id = job_entry["job_id"]
            host = job_entry["host"]

            try:
                rq_job = RQJob.fetch(job_id, connection=redis)
                status = rq_job.get_status()
                # RQ returns a JobStatus enum — convert to plain string
                status = status.value if hasattr(status, "value") else str(status)
            except Exception:
                status = "unknown"

            if status in ("finished",):
                completed += 1
            elif status in ("failed",):
                failed += 1
            else:
                pending += 1

            jobs_status.append({"job_id": job_id, "host": host, "status": status})

        return {
            "batch_id": batch_id,
            "total": len(batch_data["jobs"]),
            "completed": completed,
            "pending": pending,
            "failed": failed,
            "jobs": jobs_status,
        }
