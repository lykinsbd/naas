# API Resources

from flask_restful import Resource
from flask import request, current_app
from naas import __version__
from naas.library.decorators import valid_payload
from naas.library.netmiko_lib import netmiko_send_command
from naas.library.validation import Validate


class SendCommands(Resource):

    @staticmethod
    def get():
        return {"app": "naas", "version": __version__}

    @valid_payload
    def post(self):
        """
        Will enqueue an attempt to run commands on a device.

        Requires you submit the following in the payload:
            ip: str
            port: int
            platform: str
            username: str
            password: str
            enable: Optional[str]
            config_set: bool
            commands: Sequence[str]
        :return: A dict of the job ID and 202 response code.
        """

        # Enqueue your job, and return the job ID
        q = current_app.config["q"]
        job = q.enqueue(
            netmiko_send_command,
            ip=request.json["ip"],
            port=request.json["port"],
            platform=request.json["platform"],
            username=request.json["username"],
            password=request.json["password"],
            enable=request.json.get("enable", request.json["password"]),
            config_set=request.json["config_set"],
            commands=request.json["commands"],
        )

        return {"job_id": job.get_id(), "app": "naas", "version": __version__}, 202


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
        v.is_uuid(job_id=job_id)

        # Create our return dict
        r_dict = {
            "job_id": job_id, "status": None, "results": None, "error": None, "app": "nass", "version": __version__
        }

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
