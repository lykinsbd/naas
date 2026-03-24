"""Unit tests for RQ job callbacks."""

from unittest.mock import MagicMock

from naas.library.callbacks import on_job_complete, on_job_failure


class TestCallbacks:
    def test_on_job_complete_clears_dedup_key(self):
        """on_job_complete deletes the dedup key from Redis."""
        job = MagicMock()
        job.meta = {"dedup_key": "naas:dedup:abc123"}
        connection = MagicMock()

        on_job_complete(job, connection, result=None)

        connection.delete.assert_called_once_with("naas:dedup:abc123")

    def test_on_job_complete_no_dedup_key(self):
        """on_job_complete is a no-op when no dedup key in meta."""
        job = MagicMock()
        job.meta = {}
        connection = MagicMock()

        on_job_complete(job, connection, result=None)

        connection.delete.assert_not_called()

    def test_on_job_failure_clears_dedup_key(self):
        """on_job_failure deletes the dedup key from Redis."""
        job = MagicMock()
        job.meta = {"dedup_key": "naas:dedup:abc123"}
        connection = MagicMock()

        on_job_failure(job, connection, type=None, value=None, traceback=None)

        connection.delete.assert_called_once_with("naas:dedup:abc123")

    def test_on_job_failure_no_dedup_key(self):
        """on_job_failure is a no-op when no dedup key in meta."""
        job = MagicMock()
        job.meta = {}
        connection = MagicMock()

        on_job_failure(job, connection, type=None, value=None, traceback=None)

        connection.delete.assert_not_called()
