"""Unit tests for RQ job callbacks."""

from unittest.mock import MagicMock, patch

from naas.library.callbacks import _on_webhook_failure, on_job_complete, on_job_failure


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

    def test_on_job_complete_enqueues_webhook(self):
        """on_job_complete enqueues webhook delivery when webhook_url is in meta."""
        job = MagicMock()
        job.meta = {"webhook_url": "https://example.com/cb", "webhook_secret": "s3cret"}
        job.enqueued_at = MagicMock()
        job.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        connection = MagicMock()

        with patch("naas.library.callbacks.Queue") as mock_queue_cls:
            mock_queue = MagicMock()
            mock_queue_cls.return_value = mock_queue
            on_job_complete(job, connection, result=None)

        mock_queue_cls.assert_called_once_with("webhooks", connection=connection)
        mock_queue.enqueue.assert_called_once()
        args, kwargs = mock_queue.enqueue.call_args
        # Positional: func, url, job_id, status, enqueued_at, completed_at, secret
        assert args[1] == "https://example.com/cb"
        assert args[3] == "finished"
        assert args[6] == "s3cret"

    def test_on_job_failure_enqueues_webhook(self):
        """on_job_failure enqueues webhook delivery when webhook_url is in meta."""
        job = MagicMock()
        job.meta = {"webhook_url": "https://example.com/cb"}
        job.enqueued_at = MagicMock()
        job.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        connection = MagicMock()

        with patch("naas.library.callbacks.Queue") as mock_queue_cls:
            mock_queue = MagicMock()
            mock_queue_cls.return_value = mock_queue
            on_job_failure(job, connection, type=None, value=None, traceback=None)

        args, _ = mock_queue.enqueue.call_args
        assert args[3] == "failed"

    def test_on_job_complete_no_webhook_when_url_absent(self):
        """on_job_complete does not enqueue webhook when webhook_url not in meta."""
        job = MagicMock()
        job.meta = {}

        with patch("naas.library.callbacks.Queue") as mock_queue_cls:
            on_job_complete(job, MagicMock(), result=None)

        mock_queue_cls.assert_not_called()

    def test_on_webhook_failure_emits_audit_event(self):
        """_on_webhook_failure emits webhook.failed audit event."""
        job = MagicMock()
        job.meta = {"source_job_id": "abc-123", "webhook_url": "https://example.com/cb"}

        with patch("naas.library.callbacks.emit_audit_event") as mock_audit:
            _on_webhook_failure(job, MagicMock(), type=None, value=Exception("refused"), traceback=None)

        mock_audit.assert_called_once()
        _, kwargs = mock_audit.call_args
        assert kwargs["job_id"] == "abc-123"
        assert kwargs["webhook_url"] == "https://example.com/cb"
        assert kwargs["last_error"] == "refused"
