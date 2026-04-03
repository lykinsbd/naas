"""Unit tests for naas.library.webhook."""

from unittest.mock import MagicMock, patch

from naas.library.webhook import fire_webhook


class TestFireWebhook:
    def test_posts_notification_payload(self):
        """fire_webhook POSTs job metadata (not results) to the given URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("naas.library.webhook.requests.post", return_value=mock_response) as mock_post:
            fire_webhook(
                url="https://example.com/callback",
                job_id="abc-123",
                status="finished",
                enqueued_at="2026-01-01T00:00:00+00:00",
                completed_at="2026-01-01T00:00:05+00:00",
            )

        mock_post.assert_called_once_with(
            "https://example.com/callback",
            json={
                "job_id": "abc-123",
                "status": "finished",
                "enqueued_at": "2026-01-01T00:00:00+00:00",
                "completed_at": "2026-01-01T00:00:05+00:00",
            },
            timeout=10,
        )

    def test_swallows_connection_error(self):
        """fire_webhook does not raise on connection failure (fire-and-forget)."""
        with patch("naas.library.webhook.requests.post", side_effect=ConnectionError("refused")):
            fire_webhook(
                url="https://example.com/callback",
                job_id="abc-123",
                status="finished",
                enqueued_at="",
                completed_at="",
            )  # must not raise

    def test_swallows_http_error(self):
        """fire_webhook does not raise on non-2xx response."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("500 Server Error")

        with patch("naas.library.webhook.requests.post", return_value=mock_response):
            fire_webhook(
                url="https://example.com/callback",
                job_id="abc-123",
                status="failed",
                enqueued_at="",
                completed_at="",
            )  # must not raise
