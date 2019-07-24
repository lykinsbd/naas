# API Resources

from flask_restful import Resource
from flask import current_app, g, request
from naas import __version__
from naas.library.auth import job_locker, salted_hash
from naas.library.decorators import valid_post
from naas.library.netmiko_lib import netmiko_send_command
from werkzeug.exceptions import BadRequest, Unauthorized


class SendCommand(Resource):
    @staticmethod
    def get():
        return {"app": "naas", "version": __version__}

    @valid_post
    def post(self):
        """
        Will enqueue an attempt to run commands on a device.

        Requires you submit the following in the payload:
            ip: str
            port: int
            device_type: str
            enable: Optional[str]
            config_set: bool
            commands: Sequence[str]
        Secured by Basic Auth, which is then passed to the network device.
        :return: A dict of the job ID and 202 response code.
        """

        # Grab creds off the basic_auth header
        auth = request.authorization
        if auth.username is None:
            raise Unauthorized

        # Grab x-request-id
        request_id = g.request_id

        # Validate there isn't already a job by this ID
        q = current_app.config["q"]
        if q.fetch_job(request_id) is not None:
            raise BadRequest

        # Enqueue your job, and return the job ID
        current_app.logger.debug(
            "%s: Enqueueing job for %s@%s:%s", request_id, auth.username, request.json["ip"], request.json["port"]
        )
        job = q.enqueue(
            netmiko_send_command,
            ip=request.json["ip"],
            port=request.json["port"],
            device_type=request.json["device_type"],
            username=auth.username,
            password=auth.password,
            enable=request.json.get("enable", auth.password),
            commands=request.json["commands"],
            job_id=request_id,
        )
        job_id = job.get_id()
        current_app.logger.info(
            "%s: Enqueued job for %s@%s:%s", job_id, auth.username, request.json["ip"], request.json["port"]
        )

        # Generate the un/pw hash:
        user_hash = salted_hash(username=auth.username, password=auth.password)

        # Stash the job_id in redis, with the user/pass hash so that only that user can retrieve results
        job_locker(salted_creds=user_hash, job_id=job_id)

        # Return our payload containing job_id, a 202 Accepted, and the X-Request-ID header
        return {"job_id": job_id, "app": "naas", "version": __version__}, 202, {"X-Request-ID": job_id}
