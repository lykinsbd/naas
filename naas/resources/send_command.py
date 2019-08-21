# API Resource for wrapping netmiko's send_command() function

from flask_restful import Resource
from flask import current_app, g, request
from naas import __version__
from naas.library.auth import Credentials, job_locker, tacacs_auth_lockout
from naas.library.errorhandlers import DuplicateRequestID
from naas.library.decorators import valid_post
from naas.library.netmiko_lib import netmiko_send_command
from werkzeug.exceptions import Forbidden, Unauthorized


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
            commands: Sequence[str]
        Optional:
            port: int - Default 22
            device_type: str - Default cisco_ios
            enable: Optional[str] - Default the password provided for basic auth

        Secured by Basic Auth, which is then passed to the network device.
        :return: A dict of the job ID, a 202 response code, and the job_id as the X-Request-ID header
        """

        # Grab creds off the basic_auth header
        auth = request.authorization
        if auth.username is None:
            raise Unauthorized

        # Check if this user is locked out or not
        if tacacs_auth_lockout(username=auth.username):
            raise Forbidden

        # Create a credentials object
        creds = Credentials(username=auth.username, password=auth.password, enable=request.json.get("enable", None))

        # Grab x-request-id
        request_id = g.request_id

        # Validate there isn't already a job by this ID
        q = current_app.config["q"]
        if q.fetch_job(request_id) is not None:
            raise DuplicateRequestID

        # Enqueue your job, and return the job ID
        current_app.logger.debug(
            "%s: Enqueueing job for %s@%s:%s", request_id, creds.username, request.json["ip"], request.json["port"]
        )
        job = q.enqueue(
            netmiko_send_command,
            ip=request.json["ip"],
            port=request.json["port"],
            device_type=request.json["device_type"],
            credentials=creds,
            commands=request.json["commands"],
            job_id=request_id,
        )
        job_id = job.get_id()
        current_app.logger.info(
            "%s: Enqueued job for %s@%s:%s", job_id, creds.username, request.json["ip"], request.json["port"]
        )

        # Generate the un/pw hash:
        user_hash = creds.salted_hash()

        # Stash the job_id in redis, with the user/pass hash so that only that user can retrieve results
        job_locker(salted_creds=user_hash, job_id=job_id)

        # Return our payload containing job_id, a 202 Accepted, and the X-Request-ID header
        return {"job_id": job_id, "app": "naas", "version": __version__}, 202, {"X-Request-ID": job_id}
