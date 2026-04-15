# API Resources

from flask import current_app, request
from flask_restful import Resource
from rq.exceptions import NoSuchJobError
from rq.job import Job
from spectree import Response
from werkzeug.exceptions import Forbidden

from naas import __base_response__
from naas.library.auth import Credentials, job_unlocker, require_role
from naas.library.validation import Validate
from naas.models import JobResultResponse
from naas.spec import spec


class GetResults(Resource):
    @staticmethod
    @require_role("viewer")
    @spec.validate(resp=Response(HTTP_200=JobResultResponse))
    def get(job_id: str):
        """
        Given the requested job_id, return status and/or any results if finished.
        :param job_id:
        :return: A dict of job status and/or results if finished.
        """

        # Validate our job_id
        v = Validate()
        v.is_uuid(uuid=job_id)
        v.has_auth()

        # Ensure this user can access the job...
        auth = request.authorization
        if (
            not auth or not auth.username or not auth.password
        ):  # pragma: no cover  # has_auth() in valid_get guarantees this; guard exists because assert is stripped by python -O
            raise Forbidden

        # Create a credentials object
        creds = Credentials(username=auth.username, password=auth.password)

        # Salt the un/pw and pass that to the job_unlocker
        if not job_unlocker(salted_creds=creds.salted_hash(), job_id=job_id):
            raise Forbidden

        # Fetch your job, and return the job status and results (if it's finished)
        try:
            job = Job.fetch(job_id, connection=current_app.config["redis"])
        except NoSuchJobError:
            job = None

        if job is None:
            r = JobResultResponse(job_id=job_id, status="not_found").model_dump()
            r.update(__base_response__)
            return r, 404

        job_status = job.get_status()
        r = JobResultResponse(job_id=job_id, status=job_status).model_dump()

        if job_status == "finished":
            results = job.result
            result_dict = results[0]
            r["results"] = result_dict
            error_info = results[1]
            if hasattr(error_info, "code"):
                r["error"] = error_info.message
                r["error_code"] = error_info.code
                r["error_retryable"] = error_info.retryable
            else:
                r["error"] = error_info  # legacy plain string or None
            # Extract detected_platform if present
            if result_dict and "_detected_platform" in result_dict:
                r["detected_platform"] = result_dict.pop("_detected_platform")
        elif job_status == "failed":
            r["error"] = str(job.exc_info).strip() if job.exc_info else "Job failed"
            r["error_code"] = "UNKNOWN"
            r["error_retryable"] = False

        # Include tags if present in job metadata
        tags = getattr(job, "meta", {}).get("tags") if isinstance(getattr(job, "meta", {}), dict) else None
        if tags:
            r["tags"] = tags

        r.update(__base_response__)
        return r
