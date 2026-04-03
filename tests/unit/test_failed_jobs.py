"""Unit tests for failed_jobs resource (dead letter queue)."""

from base64 import b64encode
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch


class TestFailedJobsList:
    """Tests for GET /v1/jobs/failed."""

    def test_get_failed_jobs_no_auth(self, client):
        """GET without auth returns 401."""
        response = client.get("/v1/jobs/failed")
        assert response.status_code == 401

    def test_get_failed_jobs_empty(self, app, client):
        """GET returns empty list when no failed jobs."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.resources.failed_jobs.FailedJobRegistry") as mock_registry:
            mock_registry.return_value.get_job_ids.return_value = []
            response = client.get("/v1/jobs/failed", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200
        assert response.json["jobs"] == []
        assert response.json["total"] == 0

    def test_get_failed_jobs_returns_sanitized_jobs(self, app, client):
        """GET returns job list without credentials."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        mock_job = MagicMock()
        mock_job.id = "failed-job-123"
        mock_job.kwargs = {"ip": "192.0.2.1", "device_type": "cisco_ios", "port": 22}
        mock_job.exc_info = "NetMikoTimeoutException: timed out"
        mock_job.func_name = "naas.library.netmiko_lib.netmiko_send_command"
        mock_job.ended_at = datetime(2026, 1, 1, tzinfo=UTC)

        with patch("naas.resources.failed_jobs.FailedJobRegistry") as mock_registry:
            mock_registry.return_value.get_job_ids.return_value = ["failed-job-123"]
            with patch("naas.resources.failed_jobs.Job.fetch", return_value=mock_job):
                response = client.get("/v1/jobs/failed", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200
        assert len(response.json["jobs"]) == 1
        job = response.json["jobs"][0]
        assert job["job_id"] == "failed-job-123"
        assert job["host"] == "192.0.2.1"
        assert job["platform"] == "cisco_ios"
        assert "credentials" not in job
        assert "password" not in str(job)

    def test_get_failed_jobs_skips_missing_jobs(self, app, client):
        """GET skips jobs that no longer exist in Redis."""
        from rq.exceptions import NoSuchJobError

        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.resources.failed_jobs.FailedJobRegistry") as mock_registry:
            mock_registry.return_value.get_job_ids.return_value = ["gone-job"]
            with patch("naas.resources.failed_jobs.Job.fetch", side_effect=NoSuchJobError):
                response = client.get("/v1/jobs/failed", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200
        assert response.json["jobs"] == []

    def test_get_failed_jobs_trims_beyond_max_retain(self, app, client):
        """GET trims jobs beyond FAILED_JOB_MAX_RETAIN."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        # Create 502 job IDs (2 beyond default 500)
        job_ids = [f"job-{i}" for i in range(502)]

        with patch("naas.resources.failed_jobs.FailedJobRegistry") as mock_registry:
            with patch("naas.resources.failed_jobs.FAILED_JOB_MAX_RETAIN", 500):
                mock_registry.return_value.get_job_ids.return_value = job_ids
                with patch("naas.resources.failed_jobs.Job.fetch") as mock_fetch:
                    mock_fetch.side_effect = lambda jid, connection: (_ for _ in ()).throw(
                        __import__("rq.exceptions", fromlist=["NoSuchJobError"]).NoSuchJobError
                    )
                    response = client.get("/v1/jobs/failed", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200


class TestReplayJob:
    """Tests for POST /v1/jobs/{job_id}/replay."""

    def test_replay_no_auth(self, client):
        """POST without auth returns 401."""
        response = client.post("/v1/jobs/00000000-0000-0000-0000-000000000000/replay")
        assert response.status_code == 401

    def test_replay_invalid_uuid(self, client):
        """POST with invalid UUID returns 400."""
        auth = b64encode(b"testuser:testpass").decode()
        response = client.post("/v1/jobs/not-a-uuid/replay", headers={"Authorization": f"Basic {auth}"})
        assert response.status_code == 400

    def test_replay_job_not_found(self, app, client):
        """POST returns 404 when job not found."""
        from rq.exceptions import NoSuchJobError

        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.resources.failed_jobs.Job.fetch", side_effect=NoSuchJobError):
            response = client.post(
                "/v1/jobs/00000000-0000-0000-0000-000000000000/replay",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 404

    def test_replay_job_not_failed(self, app, client):
        """POST returns 409 when job is not in failed state."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        mock_job = MagicMock()
        mock_job.get_status.return_value.value = "finished"

        with patch("naas.resources.failed_jobs.Job.fetch", return_value=mock_job):
            response = client.post(
                "/v1/jobs/00000000-0000-0000-0000-000000000000/replay",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 409

    def test_replay_wrong_user_returns_403(self, app, client):
        """POST returns 403 when caller is not the original submitter."""
        auth = b64encode(b"wronguser:wrongpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        mock_job = MagicMock()
        mock_job.get_status.return_value.value = "failed"
        mock_job.meta = {}

        with patch("naas.resources.failed_jobs.Job.fetch", return_value=mock_job):
            with patch("naas.resources.failed_jobs.job_unlocker", return_value=False):
                response = client.post(
                    "/v1/jobs/00000000-0000-0000-0000-000000000000/replay",
                    headers={"Authorization": f"Basic {auth}"},
                )

        assert response.status_code == 403

    def test_replay_success_returns_202(self, app, client):
        """POST replays job and returns new job_id."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        mock_job = MagicMock()
        mock_job.get_status.return_value.value = "failed"
        mock_job.kwargs = {"ip": "192.0.2.1", "device_type": "cisco_ios", "commands": ["show version"]}
        mock_job.meta = {"context": "default", "webhook_url": ""}
        mock_job.func = MagicMock()

        new_job = MagicMock()
        new_job.id = "new-replay-job-id"
        new_job.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

        with patch("naas.resources.failed_jobs.Job.fetch", return_value=mock_job):
            with patch("naas.resources.failed_jobs.job_unlocker", return_value=True):
                with patch("naas.resources.failed_jobs.get_queue_for_context", return_value=(app.config["q"], 0)):
                    app.config["q"].enqueue.return_value = new_job
                    response = client.post(
                        "/v1/jobs/00000000-0000-0000-0000-000000000000/replay",
                        headers={"Authorization": f"Basic {auth}"},
                    )

        assert response.status_code == 202
        assert response.json["job_id"] == "new-replay-job-id"
        assert response.json["message"] == "Job replayed"
