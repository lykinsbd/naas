"""Unit tests for list_jobs resource."""

from base64 import b64encode
from datetime import datetime
from unittest.mock import MagicMock, patch

from rq.job import Job


class TestListJobs:
    """Test list_jobs resource."""

    def test_list_jobs_no_auth(self, client):
        """Test GET without auth returns 401."""
        response = client.get("/v1/jobs")
        assert response.status_code == 401

    def test_list_jobs_default_pagination(self, app, client):
        """Test GET with default pagination parameters."""
        auth = b64encode(b"testuser:testpass").decode()

        # Mock registries
        with (
            patch("naas.resources.list_jobs.FinishedJobRegistry") as mock_finished,
            patch("naas.resources.list_jobs.FailedJobRegistry") as mock_failed,
            patch("naas.resources.list_jobs.StartedJobRegistry") as mock_started,
            patch("naas.resources.list_jobs.Job.fetch") as mock_job_fetch,
        ):
            # Setup mock registries
            mock_finished_inst = MagicMock()
            mock_finished_inst.get_job_ids.return_value = ["job1", "job2"]
            mock_finished.return_value = mock_finished_inst

            mock_failed_inst = MagicMock()
            mock_failed_inst.get_job_ids.return_value = []
            mock_failed.return_value = mock_failed_inst

            mock_started_inst = MagicMock()
            mock_started_inst.get_job_ids.return_value = []
            mock_started.return_value = mock_started_inst

            # Mock queue
            app.config["q"].get_job_ids = MagicMock(return_value=[])

            # Mock job fetch
            mock_job = MagicMock(spec=Job)
            mock_job.id = "job1"
            mock_job.get_status.return_value = "finished"
            mock_job.created_at = datetime(2026, 2, 23, 12, 0, 0)
            mock_job.ended_at = datetime(2026, 2, 23, 12, 0, 5)
            mock_job_fetch.return_value = mock_job

            response = client.get("/v1/jobs", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200
        data = response.json
        assert "jobs" in data
        assert "pagination" in data
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 20

    def test_list_jobs_with_status_filter(self, app, client):
        """Test GET with status filter."""
        auth = b64encode(b"testuser:testpass").decode()

        with (
            patch("naas.resources.list_jobs.FinishedJobRegistry") as mock_finished,
            patch("naas.resources.list_jobs.Job.fetch") as mock_job_fetch,
        ):
            # Setup mock registry
            mock_finished_inst = MagicMock()
            mock_finished_inst.count = 5
            mock_finished_inst.get_job_ids.return_value = ["job1"]
            mock_finished.return_value = mock_finished_inst

            # Mock job fetch
            mock_job = MagicMock(spec=Job)
            mock_job.id = "job1"
            mock_job.get_status.return_value = "finished"
            mock_job.created_at = datetime(2026, 2, 23, 12, 0, 0)
            mock_job.ended_at = datetime(2026, 2, 23, 12, 0, 5)
            mock_job_fetch.return_value = mock_job

            response = client.get("/v1/jobs?status=finished", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200
        data = response.json
        assert data["pagination"]["total"] == 5

    def test_list_jobs_custom_pagination(self, app, client):
        """Test GET with custom page and per_page."""
        auth = b64encode(b"testuser:testpass").decode()

        with (
            patch("naas.resources.list_jobs.FinishedJobRegistry") as mock_finished,
            patch("naas.resources.list_jobs.FailedJobRegistry") as mock_failed,
            patch("naas.resources.list_jobs.StartedJobRegistry") as mock_started,
            patch("naas.resources.list_jobs.Job.fetch") as mock_job_fetch,
        ):
            # Setup mock registries
            mock_finished_inst = MagicMock()
            mock_finished_inst.get_job_ids.return_value = []
            mock_finished.return_value = mock_finished_inst

            mock_failed_inst = MagicMock()
            mock_failed_inst.get_job_ids.return_value = []
            mock_failed.return_value = mock_failed_inst

            mock_started_inst = MagicMock()
            mock_started_inst.get_job_ids.return_value = []
            mock_started.return_value = mock_started_inst

            # Mock queue
            app.config["q"].get_job_ids = MagicMock(return_value=[])

            mock_job_fetch.return_value = None

            response = client.get("/v1/jobs?page=2&per_page=10", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200
        data = response.json
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["per_page"] == 10

    def test_list_jobs_invalid_pagination(self, app, client):
        """Test GET with invalid pagination parameters returns 422."""
        auth = b64encode(b"testuser:testpass").decode()

        response = client.get("/v1/jobs?page=0&per_page=200", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 422
        assert isinstance(response.json, list)

    def test_list_jobs_invalid_status(self, app, client):
        """Test GET with invalid status value returns 422."""
        auth = b64encode(b"testuser:testpass").decode()

        response = client.get("/v1/jobs?status=invalid", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 422
        assert isinstance(response.json, list)

    def test_list_jobs_failed_status(self, app, client):
        """Test GET with failed status filter."""
        auth = b64encode(b"testuser:testpass").decode()

        with (
            patch("naas.resources.list_jobs.FailedJobRegistry") as mock_failed,
            patch("naas.resources.list_jobs.Job.fetch") as mock_job_fetch,
        ):
            # Setup mock registry
            mock_failed_inst = MagicMock()
            mock_failed_inst.count = 3
            mock_failed_inst.get_job_ids.return_value = ["job1"]
            mock_failed.return_value = mock_failed_inst

            # Mock job fetch
            mock_job = MagicMock(spec=Job)
            mock_job.id = "job1"
            mock_job.get_status.return_value = "failed"
            mock_job.created_at = datetime(2026, 2, 23, 12, 0, 0)
            mock_job.ended_at = datetime(2026, 2, 23, 12, 0, 5)
            mock_job_fetch.return_value = mock_job

            response = client.get("/v1/jobs?status=failed", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200
        data = response.json
        assert data["pagination"]["total"] == 3

    def test_list_jobs_started_status(self, app, client):
        """Test GET with started status filter."""
        auth = b64encode(b"testuser:testpass").decode()

        with (
            patch("naas.resources.list_jobs.StartedJobRegistry") as mock_started,
            patch("naas.resources.list_jobs.Job.fetch") as mock_job_fetch,
        ):
            # Setup mock registry
            mock_started_inst = MagicMock()
            mock_started_inst.count = 2
            mock_started_inst.get_job_ids.return_value = ["job1"]
            mock_started.return_value = mock_started_inst

            # Mock job fetch
            mock_job = MagicMock(spec=Job)
            mock_job.id = "job1"
            mock_job.get_status.return_value = "started"
            mock_job.created_at = datetime(2026, 2, 23, 12, 0, 0)
            mock_job.ended_at = None
            mock_job_fetch.return_value = mock_job

            response = client.get("/v1/jobs?status=started", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200
        data = response.json
        assert data["pagination"]["total"] == 2

    def test_list_jobs_queued_status(self, app, client):
        """Test GET with queued status filter."""
        auth = b64encode(b"testuser:testpass").decode()

        with patch("naas.resources.list_jobs.Job.fetch") as mock_job_fetch:
            # Mock queue
            app.config["q"].__len__ = MagicMock(return_value=4)
            app.config["q"].get_job_ids = MagicMock(return_value=["job1"])

            # Mock job fetch
            mock_job = MagicMock(spec=Job)
            mock_job.id = "job1"
            mock_job.get_status.return_value = "queued"
            mock_job.created_at = datetime(2026, 2, 23, 12, 0, 0)
            mock_job.ended_at = None
            mock_job_fetch.return_value = mock_job

            response = client.get("/v1/jobs?status=queued", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200
        data = response.json
        assert data["pagination"]["total"] == 4
