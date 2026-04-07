"""Unit tests for naas.library.webhook."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from naas.library.webhook import _sign_payload, fire_webhook


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

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["job_id"] == "abc-123"
        assert kwargs["headers"]["X-NAAS-Delivery"] == "abc-123"
        assert "X-NAAS-Signature" not in kwargs["headers"]

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


class TestWebhookHMAC:
    def test_sign_payload(self):
        """_sign_payload returns sha256=<hex> format."""
        sig = _sign_payload(b'{"key":"value"}', "my-secret")
        assert sig.startswith("sha256=")
        expected = hmac.new(b"my-secret", b'{"key":"value"}', hashlib.sha256).hexdigest()
        assert sig == f"sha256={expected}"

    def test_fire_webhook_includes_signature_when_secret_provided(self):
        """fire_webhook adds X-NAAS-Signature header when secret is set."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("naas.library.webhook.requests.post", return_value=mock_response) as mock_post:
            fire_webhook(
                url="https://example.com/callback",
                job_id="abc-123",
                status="finished",
                enqueued_at="2026-01-01T00:00:00+00:00",
                completed_at="2026-01-01T00:00:05+00:00",
                secret="my-secret",
            )

        _, kwargs = mock_post.call_args
        assert "X-NAAS-Signature" in kwargs["headers"]
        assert kwargs["headers"]["X-NAAS-Signature"].startswith("sha256=")

    def test_signature_is_verifiable(self):
        """Signature can be verified by the receiver using the same secret."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        secret = "test-webhook-secret"

        with patch("naas.library.webhook.requests.post", return_value=mock_response) as mock_post:
            fire_webhook(
                url="https://example.com/callback",
                job_id="abc-123",
                status="finished",
                enqueued_at="2026-01-01T00:00:00+00:00",
                completed_at="2026-01-01T00:00:05+00:00",
                secret=secret,
            )

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        sig_header = kwargs["headers"]["X-NAAS-Signature"]
        # Receiver verification
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        expected = "sha256=" + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
        assert hmac.compare_digest(sig_header, expected)
