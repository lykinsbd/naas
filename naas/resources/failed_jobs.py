"""API resources for the dead letter queue (failed jobs)."""

from datetime import UTC

from flask import current_app, request
from flask_restful import Resource
from rq.exceptions import NoSuchJobError
from rq.job import Callback, Job
from rq.registry import FailedJobRegistry

from naas import __base_response__
from naas.config import FAILED_JOB_MAX_RETAIN, JOB_TIMEOUT, JOB_TTL_FAILED, JOB_TTL_SUCCESS
from naas.library.auth import Credentials, job_locker, job_unlocker
from naas.library.callbacks import on_job_complete, on_job_failure
from naas.library.context import get_queue_for_context
from naas.library.sanitize import sanitize_error
from naas.library.validation import Validate
from naas.models import JobResponse


def _job_to_dict(job: Job) -> dict:
    """Serialize a failed job to a safe dict (no credentials)."""
    kwargs = job.kwargs or {}
    failed_at = None
    if job.ended_at:
        failed_at = job.ended_at.astimezone(UTC).isoformat()

    return {
        "job_id": job.id,
        "host": kwargs.get("ip", ""),
        "platform": kwargs.get("device_type", ""),
        "port": kwargs.get("port", 22),
        "failed_at": failed_at,
        "error": sanitize_error(job.exc_info),
        "func": job.func_name,
    }


class FailedJobs(Resource):
    """GET /v1/jobs/failed — list jobs in the failed registry."""

    @staticmethod
    def get():
        """
        List jobs in the failed (dead letter) registry.

        Returns:
            200: {"jobs": [...], "total": int}
            401: Unauthorized
        """
        v = Validate()
        v.has_auth()

        redis = current_app.config["redis"]
        registry = FailedJobRegistry(connection=redis)

        # Enforce max retain — trim oldest beyond cap
        job_ids = registry.get_job_ids()
        if len(job_ids) > FAILED_JOB_MAX_RETAIN:
            for old_id in job_ids[FAILED_JOB_MAX_RETAIN:]:
                try:
                    Job.fetch(old_id, connection=redis).delete()
                except Exception:
                    pass
            job_ids = job_ids[:FAILED_JOB_MAX_RETAIN]

        jobs = []
        for job_id in job_ids:
            try:
                job = Job.fetch(job_id, connection=redis)
                jobs.append(_job_to_dict(job))
            except NoSuchJobError:
                continue

        response = {"jobs": jobs, "total": len(jobs)}
        response.update(__base_response__)
        return response, 200


class ReplayJob(Resource):
    """POST /v1/jobs/{job_id}/replay — re-enqueue a failed job."""

    @staticmethod
    def post(job_id: str):
        """
        Re-enqueue a failed job using the caller's current credentials.

        The stored credentials are never used — the caller's Basic Auth credentials
        are substituted instead.

        Args:
            job_id: UUID of the failed job to replay.

        Returns:
            202: JobResponse (new job enqueued)
            401: Unauthorized
            403: Caller credentials don't match original job submitter
            404: Job not found in failed registry
            409: Job is not in failed state
        """
        v = Validate()
        v.is_uuid(uuid=job_id)
        v.has_auth()

        auth = request.authorization
        if (
            not auth or not auth.username or not auth.password
        ):  # pragma: no cover  # v.has_auth() guarantees auth; guard for type narrowing
            from werkzeug.exceptions import Forbidden

            raise Forbidden

        redis = current_app.config["redis"]

        try:
            job = Job.fetch(job_id, connection=redis)
        except NoSuchJobError:
            r = {"job_id": job_id, "status": "not_found"}
            r.update(__base_response__)
            return r, 404

        if job.get_status().value != "failed":
            r = {"job_id": job_id, "status": "not_failed"}
            r.update(__base_response__)
            return r, 409

        # Auth check — only the original submitter can replay
        caller_creds = Credentials(username=auth.username, password=auth.password)
        if not job_unlocker(salted_creds=caller_creds.salted_hash(), job_id=job_id):
            from werkzeug.exceptions import Forbidden

            raise Forbidden

        # Build new kwargs: original params but caller's credentials
        original_kwargs = dict(job.kwargs or {})
        original_kwargs["credentials"] = caller_creds

        # Determine routing context from original job meta
        context = job.meta.get("context", "default") if isinstance(job.meta, dict) else "default"
        q, _ = get_queue_for_context(context, redis)

        new_job = q.enqueue(
            job.func,
            **original_kwargs,
            job_timeout=JOB_TIMEOUT,
            result_ttl=JOB_TTL_SUCCESS,
            failure_ttl=JOB_TTL_FAILED,
            on_success=Callback(on_job_complete),
            on_failure=Callback(on_job_failure),
            meta={"webhook_url": job.meta.get("webhook_url", "") if isinstance(job.meta, dict) else ""},
        )

        job_locker(salted_creds=caller_creds.salted_hash(), job=new_job)

        response = JobResponse(
            job_id=new_job.id,
            message="Job replayed",
            queue_position=0,
            enqueued_at=new_job.enqueued_at.isoformat() if new_job.enqueued_at else "",
            timeout=JOB_TIMEOUT,
        ).model_dump()
        response.update(__base_response__)
        return response, 202, {"X-Request-ID": new_job.id}
