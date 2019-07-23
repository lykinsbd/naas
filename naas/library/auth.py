# Auth related functions

from flask import current_app
from hashlib import sha512


def job_locker(username: str, password: str, job_id: str) -> None:
    """
    Stash the job ID under the SHA512 (salted) hash of the username/password, so only that user can retrieve it
    :param username:
    :param password:
    :param job_id:
    :return:
    """

    redis = current_app.config["redis"]
    salt = redis.get("salt").decode()
    current_app.logger.debug("Salting %s:<redacted> with %s...", username, salt)
    pork = username + ":" + password + salt
    salt_shaker = sha512(pork.encode())
    salted_pork = salt_shaker.hexdigest()  # Particularly nice
    current_app.logger.debug("Locking job %s with %s", job_id, salted_pork)
    redis.set(job_id, salted_pork)


def job_key(username: str, password: str, job_id: str) -> bool:
    """
    Given a username/pass and the job_id, return True if this user is the one who initiated the job
    :param username:
    :param password:
    :param job_id:
    :return:
    """

    redis = current_app.config["redis"]
    salt = redis.get("salt").decode()
    current_app.logger.debug("Salting %s:<redacted> with %s...", username, salt)
    pork = username + ":" + password + salt
    salt_shaker = sha512(pork.encode())
    salted_pork = salt_shaker.hexdigest()  # Particularly nice

    try:
        maybe_pork = redis.get(job_id).decode()
        current_app.logger.debug("Attempting to unlock job %s with %s", job_id, salted_pork)
        if maybe_pork == salted_pork:
            return True
        else:
            current_app.logger.debug("Job %s returned %s", job_id, maybe_pork)
            return False
    except Exception:
        return False
