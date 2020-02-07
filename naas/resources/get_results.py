# API Resources

from flask_restful import Resource
from flask import current_app, request
from naas import __base_response__
from naas.library.auth import Credentials, job_unlocker
from naas.library.validation import Validate
from werkzeug.exceptions import Forbidden


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

        # Create a credentials object
        creds = Credentials(username=auth.username, password=auth.password)

        # Salt the un/pw and pass that to the job_unlocker
        if not job_unlocker(salted_creds=creds.salted_hash(), job_id=job_id):
            raise Forbidden

        # Create our return dict
        r_dict = {"job_id": job_id, "status": None, "results": None, "error": None}
        r_dict.update(__base_response__)

        # Fetch your job, and return the job status and results (if it's finished)
        q = current_app.config["q"]
        job = q.fetch_job(job_id)

        if job is None:
            r_dict["status"] = "not_found"
            return r_dict, 404

        job_status = job.get_status()
        r_dict["status"] = job_status

        if job_status == "finished":
            results = job.result
            r_dict["results"] = results[0]
            r_dict["error"] = results[1]

        return r_dict
