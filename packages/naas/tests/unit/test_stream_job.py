"""Unit tests for SSE job streaming endpoint."""

import json
from unittest.mock import MagicMock, patch

import pytest
from rq.exceptions import NoSuchJobError

from naas.library.auth import Credentials
from naas.resources.stream_job import (
    MAX_SSE_CONNECTIONS,
    _connections_lock,
    _format_sse,
)


@pytest.fixture
def auth():
    """Basic auth tuple matching the test app's mock job hash."""
    return ("admin", "admin")


def _set_job_hash(job, username, password):
    """Set the mock job's hash to match the given credentials."""
    creds = Credentials(username=username, password=password)
    job.meta["hash"] = creds.salted_hash()


def _make_job(status="queued", result=None, exc_info=None):
    """Create a mock RQ job."""
    job = MagicMock()
    job.id = "test-job-id"
    job.meta = {"hash": ""}
    job.get_status.return_value = status
    job.result = result
    job.exc_info = exc_info
    return job


def _collect_events(response) -> list[dict]:
    """Parse SSE events from a streaming response."""
    events = []
    for chunk in response.response:
        if isinstance(chunk, bytes):
            chunk = chunk.decode()
        for block in chunk.strip().split("\n\n"):
            if not block:
                continue
            event = {}
            for line in block.split("\n"):
                if line.startswith("event: "):
                    event["event"] = line[7:]
                elif line.startswith("data: "):
                    event["data"] = json.loads(line[6:])
            if event:
                events.append(event)
    return events


def _patch_job(job):
    """Context manager that patches Job.fetch everywhere to return the given job."""

    def side_effect(job_id, connection=None):
        if job is None:
            raise NoSuchJobError(job_id)
        return job

    return (
        patch("naas.resources.stream_job.Job.fetch", side_effect=side_effect),
        patch("naas.library.auth.Job.fetch", side_effect=side_effect),
    )


class TestStreamJob:
    """Tests for GET /v2/jobs/{id}/stream."""

    def test_streams_queued_to_finished(self, app, auth):
        """Job transitions queued → started → finished emit correct events."""
        job = _make_job()
        _set_job_hash(job, *auth)
        statuses = iter(["queued", "queued", "started", "started", "finished"])
        job.get_status.side_effect = lambda: next(statuses)
        job.result = [{"show version": "output"}, None]

        p1, p2 = _patch_job(job)
        with p1, p2, patch("naas.resources.stream_job.POLL_INTERVAL", 0):
            with app.test_client() as c:
                resp = c.get(f"/v2/jobs/{job.id}/stream", auth=auth)
                events = _collect_events(resp)

        assert resp.status_code == 200
        assert resp.content_type == "text/event-stream; charset=utf-8"
        assert len(events) == 3
        assert events[0] == {"event": "status", "data": {"job_id": "test-job-id", "status": "queued"}}
        assert events[1] == {"event": "status", "data": {"job_id": "test-job-id", "status": "started"}}
        assert events[2]["event"] == "result"
        assert events[2]["data"]["status"] == "finished"
        assert events[2]["data"]["results"] == {"show version": "output"}

    def test_streams_failed_job(self, app, auth):
        """Failed job emits result event with error."""
        job = _make_job(status="failed", exc_info="ConnectionError: timed out")
        _set_job_hash(job, *auth)

        p1, p2 = _patch_job(job)
        with p1, p2, patch("naas.resources.stream_job.POLL_INTERVAL", 0):
            with app.test_client() as c:
                resp = c.get(f"/v2/jobs/{job.id}/stream", auth=auth)
                events = _collect_events(resp)

        assert len(events) == 1
        assert events[0]["event"] == "result"
        assert events[0]["data"]["status"] == "failed"
        assert "timed out" in events[0]["data"]["error"]

    def test_job_not_found_returns_404(self, app, auth):
        """Non-existent job returns 404."""
        p1, p2 = _patch_job(None)
        with p1, p2:
            with app.test_client() as c:
                resp = c.get("/v2/jobs/no-such-id/stream", auth=auth)

        assert resp.status_code == 404

    def test_job_disappears_mid_stream(self, app, auth):
        """Job deleted from Redis mid-stream emits not_found event."""
        job = _make_job(status="queued")
        _set_job_hash(job, *auth)
        call_count = 0

        def fetch_side_effect(job_id, connection=None):
            nonlocal call_count
            call_count += 1
            # First two calls: existence check + auth check
            if call_count <= 2:
                return job
            # Generator's first fetch returns job (emits queued)
            if call_count == 3:
                return job
            raise NoSuchJobError(job_id)

        with (
            patch("naas.resources.stream_job.Job.fetch", side_effect=fetch_side_effect),
            patch("naas.library.auth.Job.fetch", side_effect=fetch_side_effect),
            patch("naas.resources.stream_job.POLL_INTERVAL", 0),
        ):
            with app.test_client() as c:
                resp = c.get(f"/v2/jobs/{job.id}/stream", auth=auth)
                events = _collect_events(resp)

        assert events[-1]["event"] == "result"
        assert events[-1]["data"]["status"] == "not_found"

    def test_wrong_credentials_returns_403(self, app):
        """Wrong credentials are rejected."""
        job = _make_job()
        _set_job_hash(job, "admin", "admin")

        p1, p2 = _patch_job(job)
        with p1, p2:
            with app.test_client() as c:
                resp = c.get(f"/v2/jobs/{job.id}/stream", auth=("admin", "wrong"))

        assert resp.status_code == 403

    def test_no_auth_returns_401(self, app):
        """Missing auth returns 401."""
        with app.test_client() as c:
            resp = c.get("/v2/jobs/some-id/stream")
        assert resp.status_code == 401

    def test_timeout_emits_timeout_event(self, app, auth):
        """Stream that exceeds timeout emits timeout event."""
        job = _make_job(status="started")
        _set_job_hash(job, *auth)

        p1, p2 = _patch_job(job)
        with (
            p1,
            p2,
            patch("naas.resources.stream_job.SSE_TIMEOUT", 0),
            patch("naas.resources.stream_job.POLL_INTERVAL", 0),
        ):
            with app.test_client() as c:
                resp = c.get(f"/v2/jobs/{job.id}/stream", auth=auth)
                events = _collect_events(resp)

        assert events[-1]["event"] == "timeout"

    def test_connection_limit_returns_429(self, app, auth):
        """Exceeding connection limit returns 429."""
        import naas.resources.stream_job as mod

        job = _make_job()
        _set_job_hash(job, *auth)

        p1, p2 = _patch_job(job)
        with p1, p2:
            with _connections_lock:
                original = mod._active_connections
                mod._active_connections = MAX_SSE_CONNECTIONS
            try:
                with app.test_client() as c:
                    resp = c.get(f"/v2/jobs/{job.id}/stream", auth=auth)
                assert resp.status_code == 429
            finally:
                with _connections_lock:
                    mod._active_connections = original

    def test_connection_counter_decrements(self, app, auth):
        """Active connection counter decrements after stream completes."""
        import naas.resources.stream_job as mod

        job = _make_job(status="finished", result=[{"output": "ok"}, None])
        _set_job_hash(job, *auth)

        before = mod._active_connections
        p1, p2 = _patch_job(job)
        with p1, p2, patch("naas.resources.stream_job.POLL_INTERVAL", 0):
            with app.test_client() as c:
                resp = c.get(f"/v2/jobs/{job.id}/stream", auth=auth)
                _collect_events(resp)

        assert mod._active_connections == before

    def test_detected_platform_extracted(self, app, auth):
        """Detected platform is extracted from results."""
        job = _make_job(
            status="finished",
            result=[{"show ver": "out", "_detected_platform": "cisco_ios"}, None],
        )
        _set_job_hash(job, *auth)

        p1, p2 = _patch_job(job)
        with p1, p2, patch("naas.resources.stream_job.POLL_INTERVAL", 0):
            with app.test_client() as c:
                resp = c.get(f"/v2/jobs/{job.id}/stream", auth=auth)
                events = _collect_events(resp)

        assert events[0]["data"]["detected_platform"] == "cisco_ios"
        assert "_detected_platform" not in events[0]["data"]["results"]


class TestFormatSse:
    """Tests for SSE message formatting."""

    def test_format_sse(self):
        data = {"job_id": "abc", "status": "queued"}
        result = _format_sse("status", data)
        assert result == f"event: status\ndata: {json.dumps(data)}\n\n"
