"""Unit tests for RQ job callbacks."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

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

    def test_on_job_complete_fires_webhook(self):
        """on_job_complete fires webhook when webhook_url is in meta."""
        job = MagicMock()
        job.meta = {"webhook_url": "https://example.com/cb"}
        job.enqueued_at = datetime(2026, 1, 1, tzinfo=UTC)

        with patch("naas.library.callbacks.fire_webhook") as mock_fire:
            on_job_complete(job, MagicMock(), result=None)

        mock_fire.assert_called_once()
        call_kwargs = mock_fire.call_args[1]
        assert call_kwargs["url"] == "https://example.com/cb"
        assert call_kwargs["status"] == "finished"
        assert call_kwargs["job_id"] == job.id

    def test_on_job_failure_fires_webhook(self):
        """on_job_failure fires webhook when webhook_url is in meta."""
        job = MagicMock()
        job.meta = {"webhook_url": "https://example.com/cb"}
        job.enqueued_at = datetime(2026, 1, 1, tzinfo=UTC)

        with patch("naas.library.callbacks.fire_webhook") as mock_fire:
            on_job_failure(job, MagicMock(), type=None, value=None, traceback=None)

        mock_fire.assert_called_once()
        assert mock_fire.call_args[1]["status"] == "failed"

    def test_on_job_complete_no_webhook_when_url_absent(self):
        """on_job_complete does not fire webhook when webhook_url not in meta."""
        job = MagicMock()
        job.meta = {}

        with patch("naas.library.callbacks.fire_webhook") as mock_fire:
            on_job_complete(job, MagicMock(), result=None)

        mock_fire.assert_not_called()
