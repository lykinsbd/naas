# Auth related functions

from datetime import datetime, timedelta
from hashlib import sha512
from uuid import uuid4

from flask import current_app
from redis import Redis

from naas.config import REDIS_HOST, REDIS_PASSWORD, REDIS_PORT


def job_locker(salted_creds: str, job_id: str) -> None:
    """
    Stash the job ID under the SHA512 (salted) hash of the username/password, so only that user can retrieve it
    :param salted_creds: The pre-salted username/password combo
    :param job_id:
    :return:
    """

    q = current_app.config["q"]
    current_app.logger.debug("Locking job %s with %s", job_id, salted_creds)
    job = q.fetch_job(job_id=job_id)
    job.meta["hash"] = salted_creds
    job.save_meta()


def job_unlocker(salted_creds: str, job_id: str) -> bool:
    """
    Given a username/pass and the job_id, return True if this user is the one who initiated the job
    :param salted_creds: The pre-salted username/password combo
    :param job_id:
    :return:
    """

    q = current_app.config["q"]

    try:
        current_app.logger.debug("Attempting to unlock job %s with %s", job_id, salted_creds)
        job = q.fetch_job(job_id=job_id)
        stored_hash = job.meta.get("hash", "")
        if stored_hash == salted_creds:
            return True
        else:
            current_app.logger.debug("Job %s returned %s", job_id, stored_hash)
            return False
    except Exception as e:
        current_app.logger.debug("Error unlocking job: %s", e)
        return False


def _is_locked_out(redis_key: str, redis: Redis, report_failure: bool = False) -> bool:
    """
    Sliding-window lockout: 10 failures within 10 minutes triggers a lockout.
    Uses a Redis sorted set with timestamps as scores for O(log N) window pruning.
    :param redis_key: Redis key for this lockout counter
    :param redis: Redis connection
    :param report_failure: Record a new failure before checking
    :return: True if locked out, False if access is allowed
    """
    window_start = (datetime.now() - timedelta(minutes=10)).timestamp()
    redis.zremrangebyscore(redis_key, 0, window_start)
    if report_failure:
        redis.zadd(redis_key, {str(uuid4()): datetime.now().timestamp()})
        redis.expire(redis_key, 600)
    return int(redis.zcard(redis_key)) >= 10  # type: ignore[arg-type]


def tacacs_auth_lockout(username: str, report_failure: bool = False) -> bool:
    """Check (and optionally record) a TACACS auth failure for a user."""
    redis = Redis(host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PASSWORD)
    return _is_locked_out(f"naas_failures_{username}", redis, report_failure)


def device_lockout(ip: str, report_failure: bool = False) -> bool:
    """Check (and optionally record) a connection failure for a device IP."""
    redis = Redis(host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PASSWORD)
    return _is_locked_out(f"naas_failures_device_{ip}", redis, report_failure)


class Credentials:
    """
    Dead simple object, built simply to hold credential information.
    We need this primarily to prevent printing of credentials in log messages.
    """

    def __init__(self, username: str, password: str, enable: str | None = None) -> None:
        """
        Instantiate our Credentials object
        :param username:
        :param password:
        :param enable:  If not provided, will set to the password.
        """

        self.username = username
        self.password = password
        if enable is None:
            self.enable = password
        else:
            self.enable = enable

    def __repr__(self):
        return f'{{"username": "{self.username}", "password": "<redacted>", "enable": "<redacted>"}}'

    def __str__(self):
        return self.username + ":<redacted>:<redacted>"

    def salted_hash(self, salt: str | None = None) -> str:
        """
        SHA512 (salted) hash the username/password and return the hexdigest
        :param salt: If not provided, we'll fetch it from Redis
        :return:
        """

        redis = current_app.config["redis"]
        if salt is None:
            salt = redis.get("naas_cred_salt").decode()
        current_app.logger.debug("Salting %s:<redacted> with %s...", self.username, salt)
        pork = self.username + ":" + self.password + salt
        salt_shaker = sha512(pork.encode())
        salted_pork = salt_shaker.hexdigest()  # Particularly nice
        return salted_pork
