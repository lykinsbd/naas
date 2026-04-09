"""Unit tests for naas.library.sanitize."""

from unittest.mock import MagicMock

from naas.library.sanitize import sanitize_error


class TestSanitizeError:
    def test_none_returns_none(self):
        """sanitize_error(None) returns None."""
        assert sanitize_error(None) is None

    def test_no_credentials_returns_unchanged(self):
        """Without credentials, error string is returned as-is."""
        assert sanitize_error("Connection timed out") == "Connection timed out"

    def test_redacts_password(self):
        """Password value is replaced with <redacted>."""
        creds = MagicMock()
        creds.password = "s3cr3t"
        creds.enable = ""
        creds.username = "admin"
        result = sanitize_error("Authentication failed for s3cr3t", creds)
        assert "s3cr3t" not in result
        assert "<redacted>" in result

    def test_redacts_enable_password(self):
        """Enable password is replaced with <redacted>."""
        creds = MagicMock()
        creds.password = "pass1"
        creds.enable = "enable123"
        creds.username = "user"
        result = sanitize_error("enable123 was rejected", creds)
        assert "enable123" not in result

    def test_redacts_username(self):
        """Username is replaced with <redacted>."""
        creds = MagicMock()
        creds.password = "pass"
        creds.enable = ""
        creds.username = "secretuser"
        result = sanitize_error("Login failed for secretuser", creds)
        assert "secretuser" not in result

    def test_empty_credential_values_not_replaced(self):
        """Empty credential values are not replaced (would corrupt the string)."""
        creds = MagicMock()
        creds.password = ""
        creds.enable = ""
        creds.username = ""
        result = sanitize_error("Some error message", creds)
        assert result == "Some error message"

    def test_none_credentials_no_redaction(self):
        """None credentials means no redaction."""
        result = sanitize_error("Error with password in it", None)
        assert result == "Error with password in it"
