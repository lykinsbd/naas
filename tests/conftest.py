import pytest
from fakeredis import FakeStrictRedis
from unittest.mock import patch, MagicMock


@pytest.fixture
def fake_redis():
    """Provide a fake Redis instance for testing (no decode for binary data)."""
    return FakeStrictRedis()


@pytest.fixture
def app():
    """Provide Flask app for testing."""
    # Mock Redis and RQ before importing app
    with patch("redis.Redis", return_value=FakeStrictRedis()):
        with patch("rq.Queue") as mock_queue:
            mock_job = MagicMock()
            mock_job.get_id.return_value = "test-job-id"
            mock_job.meta = {}
            mock_queue.return_value.enqueue.return_value = mock_job
            mock_queue.return_value.fetch_job.return_value = mock_job
            
            from naas.app import app as flask_app
            flask_app.config["TESTING"] = True
            flask_app.config["q"] = mock_queue.return_value
            yield flask_app


@pytest.fixture
def client(app):
    """Provide Flask test client."""
    return app.test_client()
