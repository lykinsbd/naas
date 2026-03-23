from unittest.mock import MagicMock, patch

import pytest
from fakeredis import FakeStrictRedis


@pytest.fixture
def fake_redis():
    """Provide a fake Redis instance for testing (no decode for binary data)."""
    return FakeStrictRedis()


def _make_mock_worker(queue_names: list[str]) -> MagicMock:
    """Create a mock RQ worker serving the given queue names."""
    worker = MagicMock()
    worker.queue_names.return_value = queue_names
    return worker


@pytest.fixture
def app():
    """Provide Flask app for testing."""
    # Mock Redis and RQ before importing app
    with patch("naas.config.Redis", return_value=FakeStrictRedis()):
        with patch("naas.config.Queue") as mock_queue:
            mock_job = MagicMock()
            mock_job.id = "test-job-id"
            mock_job.meta = {}
            mock_job.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
            mock_queue.return_value.enqueue.return_value = mock_job
            mock_queue.return_value.job_ids = []

            # Make fetch_job return None for new job IDs (not duplicates)
            def fetch_job_side_effect(job_id):
                if job_id == "test-job-id":
                    return mock_job
                return None

            mock_queue.return_value.fetch_job.side_effect = fetch_job_side_effect

            from naas.app import app as flask_app

            flask_app.config["TESTING"] = True
            flask_app.config["q"] = mock_queue.return_value
            yield flask_app


@pytest.fixture
def client(app):
    """Provide Flask test client."""
    return app.test_client()
