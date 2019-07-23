# Auth related functions

from flask import current_app
from hashlib import sha512
from typing import Optional


def salted_hash(username: str, password: str, salt: Optional[str] = None) -> str:
    """
    SHA512 (salted) hash the username/password and return the hexdigest
    :param username:
    :param password:
    :param salt: If not provided, we'll fetch it from Redis
    :return:
    """

    redis = current_app.config["redis"]
    if salt is None:
        salt = redis.get("salt").decode()
    current_app.logger.debug("Salting %s:<redacted> with %s...", username, salt)
    pork = username + ":" + password + salt
    salt_shaker = sha512(pork.encode())
    salted_pork = salt_shaker.hexdigest()  # Particularly nice
    return salted_pork


def job_locker(salted_creds: str, job_id: str) -> None:
    """
    Stash the job ID under the SHA512 (salted) hash of the username/password, so only that user can retrieve it
    :param salted_creds: The pre-salted username/password combo
    :param job_id:
    :return:
    """

    redis = current_app.config["redis"]
    current_app.logger.debug("Locking job %s with %s", job_id, salted_creds)
    redis.set(job_id, salted_creds)


def job_unlocker(salted_creds: str, job_id: str) -> bool:
    """
    Given a username/pass and the job_id, return True if this user is the one who initiated the job
    :param salted_creds: The pre-salted username/password combo
    :param job_id:
    :return:
    """

    redis = current_app.config["redis"]

    try:
        maybe_right = redis.get(job_id).decode()
        current_app.logger.debug("Attempting to unlock job %s with %s", job_id, salted_creds)
        if maybe_right == salted_creds:
            return True
        else:
            current_app.logger.debug("Job %s returned %s", job_id, maybe_right)
            return False
    except Exception:
        return False
