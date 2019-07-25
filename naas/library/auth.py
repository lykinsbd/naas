# Auth related functions

from datetime import datetime, timedelta
from flask import current_app
from hashlib import sha512
from pickle import dumps, loads
from naas.config import REDIS_HOST, REDIS_PORT
from redis import Redis
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
        salt = redis.get("naas_cred_salt").decode()
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


def tacacs_auth_lockout(username: str, report_failure: bool = False) -> bool:
    """
    Upon a TACACS authentication failure, as seen by Netmiko, update a dict in Redis that holds failures for this user.
    And if we've exceeded 10 failures in 10 minutes, lock this user out of the API for 10 minutes
    :param username: What username are we checking on a failure count for?
    :param report_failure: Are we reporting a new failure?  True for yes, False for no.
    :return: False for access is still allowed, True for access is now locked out for ten minutes
    """

    # Can't use current_app.BLAH as we're not always in a Flask context for this, but sometimes in the RQ worker process
    redis = Redis(host=REDIS_HOST, port=REDIS_PORT)

    # Get (or set) the current_failures entry for this hash
    failures = redis.hgetall("naas_failures_" + username)

    # Check if there are any existing login failures
    if failures:
        failure_count = int(failures[b"failure_count"])  # Its in redis as a bytes object, need to cast that to int
        failure_timestamps = loads(failures[b"failure_timestamps"])  # Need to un-pickle the list/bytes blob

        # If there are less than 9 failures, append the count, stash our timestamp, and return True
        if failure_count < 9:
            if report_failure:
                report_tacacs_failure(
                    username=username,
                    existing_fail_count=failure_count,
                    existing_fail_times=failure_timestamps,
                    redis=redis,
                )
            return False

        # If there are at least 9 failures (and potentially this is the tenth), lets dig in some.
        elif failure_count >= 9:

            # Evaluate the timestamps of previous failures, if they're more than ten minutes ago, delete and carry on
            for timestamp in loads(failures[b"failure_timestamps"]):
                if timestamp < datetime.now() - timedelta(minutes=10):
                    failure_timestamps.remove(timestamp)
                    failure_count = failure_count - 1

            # If we _still_ have 9 or more failures, they're from the past 10 minutes
            if failure_count >= 9:
                if report_failure:
                    # And... this makes 10 or more, return False
                    report_tacacs_failure(
                        username=username,
                        existing_fail_count=failure_count,
                        existing_fail_times=failure_timestamps,
                        redis=redis,
                    )
                    return True
                elif failure_count == 9:
                    # There were 9 failures in the last 10 minutes, but we're not reporting a new one, you're still good
                    return False
                else:
                    # There are 10 or more failures in past 10 minutes, nope good sir/madame, you're not getting in
                    return True

            # Now we can add our current failure (if any) and return True:
            if report_failure:
                report_tacacs_failure(
                    username=username,
                    existing_fail_count=failure_count,
                    existing_fail_times=failure_timestamps,
                    redis=redis,
                )
            return False

    # If there aren't any existing failures, update Redis with a failure value for this user
    else:
        if report_failure:
            report_tacacs_failure(username=username, existing_fail_count=0, existing_fail_times=[], redis=redis)
        return False


def report_tacacs_failure(username: str, existing_fail_count: int, existing_fail_times: list, redis: Redis) -> None:
    """
    Given a failure count and list of timestamps, increment them and stash the results in Redis
    :param username: Who dun goofed?
    :param existing_fail_count: How many failures were in the data (before this one we're reporting)
    :param existing_fail_times: List of failure times (before this one)
    :param redis: What instantiated Redis object/connection are we using
    :return:
    """

    # Update the timestamps list with a failure for right now
    existing_fail_times.append(datetime.now())
    # Pickle this list for Redis insertion
    failure_timestamps = dumps(existing_fail_times)

    # Setup our failed dict we're stashing in Redis:
    failed_dict = {"failure_count": existing_fail_count + 1, "failure_timestamps": failure_timestamps}
    redis.hmset("naas_failures_" + username, failed_dict)
