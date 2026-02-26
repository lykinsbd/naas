"""Unit tests for validation functions."""

import pytest
from flask import Flask
from werkzeug.exceptions import BadRequest

from naas.library.errorhandlers import NoAuth, NoJSON
from naas.library.validation import Validate


@pytest.fixture
def validation_app():
    """Create a minimal Flask app for validation testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["q"] = None  # Mock queue
    return app


class TestValidateIsJson:
    """Tests for Validate.is_json()."""

    def test_valid_json_passes(self, validation_app):
        """Valid JSON content should pass validation."""
        with validation_app.test_request_context(
            "/test", method="POST", json={"key": "value"}, content_type="application/json"
        ):
            Validate.is_json()  # Should not raise

    def test_no_json_raises_error(self, validation_app):
        """Request with empty JSON should raise NoJSON."""
        with validation_app.test_request_context("/test", method="POST", json={}):
            with pytest.raises(NoJSON):
                Validate.is_json()


class TestValidateHasAuth:
    """Tests for Validate.has_auth()."""

    def test_valid_auth_passes(self, validation_app):
        """Valid basic auth should pass validation."""
        with validation_app.test_request_context(
            "/test", method="POST", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        ):
            Validate.has_auth()  # Should not raise

    def test_no_auth_raises_error(self, validation_app):
        """Request without auth should raise NoAuth."""
        with validation_app.test_request_context("/test", method="POST"):
            with pytest.raises(NoAuth):
                Validate.has_auth()

    def test_missing_username_raises_error(self, validation_app):
        """Auth without username should raise NoAuth."""
        with validation_app.test_request_context("/test", method="POST"):
            from flask import request
            from werkzeug.datastructures import Authorization

            request.authorization = Authorization({"username": None, "password": "pass"})
            with pytest.raises(NoAuth):
                Validate.has_auth()


class TestValidateIsUuid:
    """Tests for Validate.is_uuid()."""

    def test_valid_uuid_passes(self, validation_app):
        """Valid UUID v4 should pass."""
        with validation_app.test_request_context("/test"):
            Validate.is_uuid("550e8400-e29b-41d4-a716-446655440000")  # Should not raise

    def test_invalid_uuid_raises_badrequest(self, validation_app):
        """Invalid UUID should raise BadRequest."""
        with validation_app.test_request_context("/test"):
            with pytest.raises(BadRequest):
                Validate.is_uuid("not-a-uuid")


class TestValidateLockedOut:
    """Tests for Validate.locked_out()."""

    def test_locked_out_user_raises_error(self, validation_app):
        """User that is locked out should raise LockedOut."""
        from unittest.mock import patch

        from naas.library.errorhandlers import LockedOut

        with validation_app.test_request_context(
            "/test", method="POST", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        ):
            with patch("naas.library.validation.tacacs_auth_lockout", return_value=True):
                with pytest.raises(LockedOut):
                    Validate.locked_out()


class TestValidateDuplicateRequestId:
    """Tests for Validate.is_duplicate_job()."""

    def test_duplicate_job_id_raises_error(self, validation_app):
        """Duplicate job_id should raise DuplicateRequestID."""
        from unittest.mock import MagicMock

        from naas.library.errorhandlers import DuplicateRequestID

        mock_queue = MagicMock()
        mock_queue.fetch_job.return_value = MagicMock()  # Job exists
        validation_app.config["q"] = mock_queue

        with validation_app.app_context():
            with pytest.raises(DuplicateRequestID):
                Validate.is_duplicate_job("existing-job-id")
