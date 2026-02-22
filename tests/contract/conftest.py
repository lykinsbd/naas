"""Pytest configuration for contract tests."""

from unittest.mock import MagicMock, patch

import pytest
from fakeredis import FakeStrictRedis


@pytest.fixture(scope="session", autouse=True)
def mock_redis():
    """Mock Redis connection for all contract tests."""
    fake_redis = FakeStrictRedis(decode_responses=False)
    with patch("redis.Redis", return_value=fake_redis):
        yield fake_redis


@pytest.fixture(scope="session")
def mock_rq_queue():
    """Mock RQ Queue for all contract tests."""
    mock_job = MagicMock()
    mock_job.get_id.return_value = "12345678-1234-4234-8234-123456789abc"
    mock_job.get_status.return_value = "queued"
    mock_job.meta = {}
    mock_job.save_meta = MagicMock()

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_job
    mock_queue.fetch_job.return_value = mock_job

    return mock_queue


@pytest.fixture(autouse=True)
def reset_mock_job_meta(mock_rq_queue):
    """Reset job meta between tests."""
    mock_rq_queue.enqueue.return_value.meta = {}
    yield
