"""SSE streaming endpoint for real-time job status updates."""

import json
import threading
import time
from collections.abc import Generator

from flask import Response, current_app, request
from flask_restful import Resource
from rq.exceptions import NoSuchJobError
from rq.job import Job
from werkzeug.exceptions import Forbidden, NotFound, TooManyRequests

from naas.library.auth import Credentials, job_unlocker, require_role

#: Maximum concurrent SSE connections across all workers in this process.
MAX_SSE_CONNECTIONS = 100

#: Server-side timeout for SSE connections in seconds (5 minutes).
SSE_TIMEOUT = 300

#: Interval between Redis polls in seconds.
POLL_INTERVAL = 1.0

_active_connections = 0
_connections_lock = threading.Lock()

#: Terminal job statuses that close the SSE stream.
_TERMINAL = frozenset({"finished", "failed", "canceled", "cancelled"})


def _format_sse(event: str, data: dict) -> str:
    """Format a single SSE message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _build_event(job_id: str, job: Job | None, status: str) -> tuple[str, dict]:
    """Build an SSE event tuple (event_type, data) from job state."""
    data: dict = {"job_id": job_id, "status": status}

    if status == "finished" and job is not None and job.result is not None:
        results = job.result
        data["results"] = results[0]
        error_info = results[1]
        if hasattr(error_info, "code"):
            data["error"] = error_info.message
            data["error_code"] = error_info.code
            data["error_retryable"] = error_info.retryable
        else:
            data["error"] = error_info  # legacy plain string or None
        if results[0] and "_detected_platform" in results[0]:
            data["detected_platform"] = results[0].pop("_detected_platform")
        return "result", data

    if status == "failed" and job is not None:
        data["error"] = str(job.exc_info).strip() if job.exc_info else "Job failed"
        data["error_code"] = "UNKNOWN"
        data["error_retryable"] = False
        return "result", data

    return "status", data


class StreamJob(Resource):
    """Stream job status updates via Server-Sent Events."""

    @require_role("viewer")
    def get(self, job_id: str) -> Response:
        """Open an SSE stream for the given job.

        Args:
            job_id: The job UUID to stream.

        Returns:
            A streaming ``text/event-stream`` response.
        """
        # --- verify job exists ---
        redis = current_app.config["redis"]
        try:
            Job.fetch(job_id, connection=redis)
        except NoSuchJobError:
            raise NotFound(f"Job {job_id} not found")

        # --- auth (same as GetResults) ---
        auth = request.authorization
        if not auth or not auth.username or not auth.password:  # pragma: no cover
            raise Forbidden

        creds = Credentials(username=auth.username, password=auth.password)
        if not job_unlocker(salted_creds=creds.salted_hash(), job_id=job_id):
            raise Forbidden

        # --- connection limit ---
        global _active_connections  # noqa: PLW0603
        with _connections_lock:
            if _active_connections >= MAX_SSE_CONNECTIONS:
                raise TooManyRequests("SSE connection limit reached")
            _active_connections += 1

        # Capture redis ref outside request context for the generator
        redis_conn = redis

        def generate() -> Generator[str, None, None]:
            global _active_connections  # noqa: PLW0603
            try:
                last_status = None
                deadline = time.monotonic() + SSE_TIMEOUT

                while time.monotonic() < deadline:
                    try:
                        job = Job.fetch(job_id, connection=redis_conn)
                        status = job.get_status()
                    except NoSuchJobError:
                        yield _format_sse("result", {"job_id": job_id, "status": "not_found"})
                        return

                    if status != last_status:
                        event_type, data = _build_event(job_id, job, status)
                        yield _format_sse(event_type, data)
                        last_status = status

                        if status in _TERMINAL:
                            return

                    time.sleep(POLL_INTERVAL)

                # Timeout reached
                yield _format_sse("timeout", {"job_id": job_id, "message": "Stream timeout"})
            finally:
                with _connections_lock:
                    _active_connections -= 1

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
