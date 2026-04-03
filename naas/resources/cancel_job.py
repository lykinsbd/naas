"""API resource for job cancellation."""

from flask import current_app, request
from flask_restful import Resource
from rq.exceptions import NoSuchJobError
from rq.job import Job
from werkzeug.exceptions import Conflict, Forbidden

from naas import __base_response__
from naas.library.audit import emit_audit_event
from naas.library.auth import Credentials, job_unlocker
from naas.library.validation import Validate


class CancelJob(Resource):
    """Resource for cancelling jobs."""

    @staticmethod
    def delete(job_id: str):
        """
        Cancel a job by job_id.

        Args:
            job_id: UUID of the job to cancel.

        Returns:
            Empty response with 204 status on success.
            400 if job_id is not a valid UUID.
            403 if credentials do not match the job submitter.
            404 if job not found.
            409 if job already finished or failed.
        """
        v = Validate()
        v.is_uuid(uuid=job_id)
        v.has_auth()

        auth = request.authorization
        if (
            not auth or not auth.username or not auth.password
        ):  # pragma: no cover  # v.has_auth() above guarantees auth is present; guard exists for type narrowing
            raise Forbidden

        # Check job exists before auth check (404 > 403)
        try:
            job = Job.fetch(job_id, connection=current_app.config["redis"])
        except NoSuchJobError:
            r = {"job_id": job_id, "status": "not_found"}
            r.update(__base_response__)
            return r, 404

        creds = Credentials(username=auth.username, password=auth.password)
        if not job_unlocker(salted_creds=creds.salted_hash(), job_id=job_id):
            raise Forbidden

        job_status = job.get_status()
        if job_status in ("finished", "failed"):
            raise Conflict(f"Job {job_id} already {job_status}")

        job.cancel()

        emit_audit_event("job.cancelled", request_id=job_id, cancelled_by_hash=creds.salted_hash())

        return "", 204
