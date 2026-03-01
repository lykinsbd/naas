"""API resource for job cancellation."""

from flask import current_app, request
from flask_restful import Resource
from werkzeug.exceptions import Conflict, Forbidden

from naas import __base_response__
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
            404 if job not found.
            403 if wrong credentials.
            409 if job already finished or failed.
        """
        v = Validate()
        v.is_uuid(uuid=job_id)
        v.has_auth()

        auth = request.authorization
        if not auth or not auth.username or not auth.password:  # pragma: no cover
            raise Forbidden

        creds = Credentials(username=auth.username, password=auth.password)
        if not job_unlocker(salted_creds=creds.salted_hash(), job_id=job_id):
            raise Forbidden

        q = current_app.config["q"]
        job = q.fetch_job(job_id)

        if job is None:
            r = {"job_id": job_id, "status": "not_found"}
            r.update(__base_response__)
            return r, 404

        job_status = job.get_status()
        if job_status in ("finished", "failed"):
            raise Conflict(f"Job {job_id} already {job_status}")

        job.cancel()
        return "", 204
