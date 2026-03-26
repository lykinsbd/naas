"""Unit tests for Pydantic model validation."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from naas.models import SendCommandRequest, SendConfigRequest


class TestTagsValidation:
    """Direct model validation tests for the tags field."""

    def _base(self):
        return {"host": "192.0.2.1", "commands": ["show version"]}

    def test_valid_tags_accepted(self):
        """Tags with valid keys/values are accepted."""
        r = SendCommandRequest(**self._base(), tags={"change": "CHG001", "site": "nyc-dc1"})
        assert r.tags == {"change": "CHG001", "site": "nyc-dc1"}

    def test_none_tags_accepted(self):
        """None tags (omitted) is valid."""
        r = SendCommandRequest(**self._base())
        assert r.tags is None

    def test_validate_tags_none_directly(self):
        """_validate_tags returns None when called directly with None."""
        from naas.models import _validate_tags

        assert _validate_tags(None) is None

    def test_too_many_tags_rejected(self):
        """More than 10 tags raises ValidationError."""
        with pytest.raises(ValidationError, match="at most 10"):
            SendCommandRequest(**self._base(), tags={f"key{i}": f"val{i}" for i in range(11)})

    def test_invalid_tag_key_rejected(self):
        """Tag key with spaces raises ValidationError."""
        with pytest.raises(ValidationError, match="tag key"):
            SendCommandRequest(**self._base(), tags={"invalid key!": "value"})

    def test_invalid_tag_value_rejected(self):
        """Tag value with special chars raises ValidationError."""
        with pytest.raises(ValidationError, match="tag value"):
            SendCommandRequest(**self._base(), tags={"key": "invalid value!"})

    def test_send_config_too_many_tags_rejected(self):
        """SendConfigRequest also enforces max 10 tags."""
        with pytest.raises(ValidationError, match="at most 10"):
            SendConfigRequest(
                host="192.0.2.1",
                commands=["interface Gi0/1"],
                tags={f"key{i}": f"val{i}" for i in range(11)},
            )

    def test_send_config_invalid_tag_key_rejected(self):
        """SendConfigRequest rejects invalid tag keys."""
        with pytest.raises(ValidationError, match="tag key"):
            SendConfigRequest(
                host="192.0.2.1",
                commands=["interface Gi0/1"],
                tags={"bad key!": "value"},
            )

    def test_send_config_invalid_tag_value_rejected(self):
        """SendConfigRequest rejects invalid tag values."""
        with pytest.raises(ValidationError, match="tag value"):
            SendConfigRequest(
                host="192.0.2.1",
                commands=["interface Gi0/1"],
                tags={"key": "bad value!"},
            )


class TestWebhookUrlValidation:
    def test_https_url_accepted(self):
        """HTTPS webhook_url is accepted."""
        from naas.models import SendCommandRequest

        req = SendCommandRequest(host="192.0.2.1", commands=["show version"], webhook_url="https://example.com/cb")
        assert req.webhook_url == "https://example.com/cb"

    def test_none_accepted(self):
        """webhook_url=None is accepted (optional field)."""
        from naas.models import SendCommandRequest, _validate_webhook_url

        req = SendCommandRequest(host="192.0.2.1", commands=["show version"])
        assert req.webhook_url is None
        # Test the validator directly to ensure None early-return is covered
        assert _validate_webhook_url(None) is None

    def test_http_rejected_by_default(self):
        """HTTP webhook_url is rejected when WEBHOOK_ALLOW_HTTP=false."""
        from naas.models import SendCommandRequest

        with patch("naas.config.WEBHOOK_ALLOW_HTTP", False):
            with pytest.raises(ValidationError, match="https"):
                SendCommandRequest(host="192.0.2.1", commands=["show version"], webhook_url="http://example.com/cb")

    def test_http_allowed_when_flag_set(self):
        """HTTP webhook_url is accepted when WEBHOOK_ALLOW_HTTP=true."""
        from naas.models import _validate_webhook_url

        with patch("naas.config.WEBHOOK_ALLOW_HTTP", True):
            result = _validate_webhook_url("http://example.com/cb")
        assert result == "http://example.com/cb"

    def test_invalid_url_rejected(self):
        """Non-URL string is rejected."""
        from naas.models import SendCommandRequest

        with pytest.raises(ValidationError, match="https"):
            SendCommandRequest(host="192.0.2.1", commands=["show version"], webhook_url="not-a-url")

    def test_send_config_https_accepted(self):
        """SendConfigRequest also validates webhook_url."""
        req = SendConfigRequest(host="192.0.2.1", commands=["interface Gi0/1"], webhook_url="https://example.com/cb")
        assert req.webhook_url == "https://example.com/cb"
