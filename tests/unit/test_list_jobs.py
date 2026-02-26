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
            mock_finished_inst.count = 2
            mock_finished_inst.get_job_ids.return_value = ["job1", "job2"]
            mock_finished.return_value = mock_finished_inst

            mock_failed_inst = MagicMock()
            mock_failed_inst.count = 0
            mock_failed_inst.get_job_ids.return_value = []
            mock_failed.return_value = mock_failed_inst

            mock_started_inst = MagicMock()
            mock_started_inst.count = 0
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
            mock_finished_inst.count = 0
            mock_finished_inst.get_job_ids.return_value = []
            mock_finished.return_value = mock_finished_inst

            mock_failed_inst = MagicMock()
            mock_failed_inst.count = 0
            mock_failed_inst.get_job_ids.return_value = []
            mock_failed.return_value = mock_failed_inst

            mock_started_inst = MagicMock()
            mock_started_inst.count = 0
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

    def test_list_jobs_unfiltered_stops_early(self, app, client):
        """Unfiltered pagination: stops iterating sources once per_page is satisfied."""
        auth = b64encode(b"testuser:testpass").decode()

        with (
            patch("naas.resources.list_jobs.FinishedJobRegistry") as mock_finished,
            patch("naas.resources.list_jobs.FailedJobRegistry") as mock_failed,
            patch("naas.resources.list_jobs.StartedJobRegistry") as mock_started,
            patch("naas.resources.list_jobs.Job.fetch") as mock_job_fetch,
        ):
            mock_finished_inst = MagicMock()
            mock_finished_inst.count = 1
            mock_finished_inst.get_job_ids.return_value = ["job1"]
            mock_finished.return_value = mock_finished_inst

            mock_failed_inst = MagicMock()
            mock_failed_inst.count = 1
            mock_failed_inst.get_job_ids.return_value = ["job2"]
            mock_failed.return_value = mock_failed_inst

            mock_started_inst = MagicMock()
            mock_started_inst.count = 0
            mock_started_inst.get_job_ids.return_value = []
            mock_started.return_value = mock_started_inst

            app.config["q"].__len__ = MagicMock(return_value=0)
            app.config["q"].get_job_ids = MagicMock(return_value=[])

            mock_job = MagicMock(spec=Job)
            mock_job.id = "job1"
            mock_job.get_status.return_value = "finished"
            mock_job.created_at = datetime(2026, 2, 23, 12, 0, 0)
            mock_job.ended_at = datetime(2026, 2, 23, 12, 0, 5)
            mock_job_fetch.return_value = mock_job

            # per_page=1 means finished fills the page; failed registry should not be fetched
            response = client.get("/v1/jobs?per_page=1", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200
        data = response.json
        assert data["pagination"]["total"] == 2
        assert len(data["jobs"]) == 1
        mock_failed_inst.get_job_ids.assert_not_called()
        """Unfiltered pagination: page 2 skips finished registry and pulls from queue."""
        auth = b64encode(b"testuser:testpass").decode()

        with (
            patch("naas.resources.list_jobs.FinishedJobRegistry") as mock_finished,
            patch("naas.resources.list_jobs.FailedJobRegistry") as mock_failed,
            patch("naas.resources.list_jobs.StartedJobRegistry") as mock_started,
            patch("naas.resources.list_jobs.Job.fetch") as mock_job_fetch,
        ):
            mock_finished_inst = MagicMock()
            mock_finished_inst.count = 1  # page 2 skips this entirely
            mock_finished_inst.get_job_ids.return_value = []
            mock_finished.return_value = mock_finished_inst

            mock_failed_inst = MagicMock()
            mock_failed_inst.count = 0
            mock_failed_inst.get_job_ids.return_value = []
            mock_failed.return_value = mock_failed_inst

            mock_started_inst = MagicMock()
            mock_started_inst.count = 0
            mock_started_inst.get_job_ids.return_value = []
            mock_started.return_value = mock_started_inst

            # Queue has the job for page 2
            app.config["q"].__len__ = MagicMock(return_value=1)
            app.config["q"].get_job_ids = MagicMock(return_value=["job2"])

            mock_job = MagicMock(spec=Job)
            mock_job.id = "job2"
            mock_job.get_status.return_value = "queued"
            mock_job.created_at = datetime(2026, 2, 23, 12, 0, 0)
            mock_job.ended_at = None
            mock_job_fetch.return_value = mock_job

            response = client.get("/v1/jobs?page=2&per_page=1", headers={"Authorization": f"Basic {auth}"})

        assert response.status_code == 200
        data = response.json
        assert data["pagination"]["total"] == 2  # 1 finished + 1 queued
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["job_id"] == "job2"
        # Verify queue was called (is_queue branch) and finished registry was skipped
        app.config["q"].get_job_ids.assert_called_once_with(offset=0, length=1)
