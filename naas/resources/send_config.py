# API Resource for wrapping netmiko's send_config() function

from flask import current_app, g, request
from flask_restful import Resource

from naas import __base_response__
from naas.library.auth import job_locker
from naas.library.decorators import valid_post
from naas.library.netmiko_lib import netmiko_send_config
from naas.models import SendConfigRequest, validate_request


class SendConfig(Resource):
    @staticmethod
    def get():
        return __base_response__

    @valid_post
    def post(self):
        """
        Will enqueue an attempt to use netmiko's send_config_set() method to run commands/put configuration on a device.

        Requires you submit the following in the payload:
            ip: str
            commands: Sequence[str]
        Optional:
            port: int - Default 22
            platform: str - Default cisco_ios
            enable: Optional[str] - Default the password provided for basic auth
            save_config: bool
            commit: bool

        Secured by Basic Auth, which is then passed to the network device.
        :return: A dict of the job ID, a 202 response code, and the job_id as the X-Request-ID header
        """
        # Validate request with Pydantic
        result = validate_request(SendConfigRequest, request.json)
        if not isinstance(result, SendConfigRequest):
            return result
        validated = result

        ip_str = str(validated.ip)

        # Enqueue your job, and return the job ID
        current_app.logger.debug(
            "%s: Enqueueing job for %s@%s:%s",
            g.request_id,
            g.credentials.username,
            ip_str,
            validated.port,
        )
        job = current_app.config["q"].enqueue(
            netmiko_send_config,
            ip=ip_str,
            port=validated.port,
            device_type=validated.platform,
            credentials=g.credentials,
            commands=validated.config,
            save_config=validated.save_config,
            commit=validated.commit,
            delay_factor=validated.delay_factor,
            job_id=g.request_id,
            result_ttl=86460,
            failure_ttl=86460,
        )
        job_id = job.get_id()
        current_app.logger.info("%s: Enqueued job for %s@%s:%s", job_id, g.credentials.username, ip_str, validated.port)

        # Generate the un/pw hash:
        user_hash = g.credentials.salted_hash()

        # Stash the job_id in redis, with the user/pass hash so that only that user can retrieve results
        job_locker(salted_creds=user_hash, job_id=job_id)

        # Return our payload containing job_id added to the base response, a 202 Accepted, and the X-Request-ID header
        response = {"job_id": job_id}
        response.update(__base_response__)
        return response, 202, {"X-Request-ID": job_id}
