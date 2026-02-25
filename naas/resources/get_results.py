# API Resources

from flask import current_app, request
from flask_restful import Resource
from werkzeug.exceptions import Forbidden

from naas import __base_response__
from naas.library.auth import Credentials, job_unlocker
from naas.library.validation import Validate
from naas.models import JobResultResponse


class GetResults(Resource):
    @staticmethod
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
        if not auth or not auth.username or not auth.password:  # pragma: no cover
            raise Forbidden

        # Create a credentials object
        creds = Credentials(username=auth.username, password=auth.password)

        # Salt the un/pw and pass that to the job_unlocker
        if not job_unlocker(salted_creds=creds.salted_hash(), job_id=job_id):
            raise Forbidden

        # Fetch your job, and return the job status and results (if it's finished)
        q = current_app.config["q"]
        job = q.fetch_job(job_id)

        if job is None:
            r = JobResultResponse(job_id=job_id, status="not_found").model_dump()
            r.update(__base_response__)
            return r, 404

        job_status = job.get_status()
        r = JobResultResponse(job_id=job_id, status=job_status).model_dump()

        if job_status == "finished":
            results = job.result
            r["results"] = results[0]
            r["error"] = results[1]

        r.update(__base_response__)
        return r
