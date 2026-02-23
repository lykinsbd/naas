"""Unit tests for validation functions."""

import pytest
from flask import Flask
from werkzeug.exceptions import BadRequest, UnprocessableEntity

from naas.library.errorhandlers import InvalidIP, NoAuth, NoJSON
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
            # Empty JSON dict is falsy, should raise NoJSON
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
        # Empty username in basic auth (":pass" base64 encoded)
        with validation_app.test_request_context("/test", method="POST"):
            from flask import request
            from werkzeug.datastructures import Authorization

            request.authorization = Authorization({"username": None, "password": "pass"})
            with pytest.raises(NoAuth):
                Validate.has_auth()


class TestValidateHasPort:
    """Tests for Validate.has_port()."""

    def test_sets_default_port(self, validation_app):
        """Should set port to 22 if not provided."""
        with validation_app.test_request_context("/test", method="POST", json={}):
            from flask import request

            Validate.has_port()
            assert request.json["port"] == 22

    def test_preserves_existing_port(self, validation_app):
        """Should preserve port if already set."""
        with validation_app.test_request_context("/test", method="POST", json={"port": 2222}):
            from flask import request

            Validate.has_port()
            assert request.json["port"] == 2222


class TestValidateIsIpAddr:
    """Tests for Validate.is_ip_addr()."""

    def test_valid_ipv4_passes(self, validation_app):
        """Valid IPv4 address should pass."""
        with validation_app.test_request_context("/test", method="POST", json={"ip": "192.168.1.1"}):
            Validate.is_ip_addr()  # Should not raise

    def test_missing_ip_raises_badrequest(self, validation_app):
        """Missing IP field should raise BadRequest."""
        with validation_app.test_request_context("/test", method="POST", json={}):
            with pytest.raises(BadRequest):
                Validate.is_ip_addr()

    def test_invalid_ip_raises_invalidip(self, validation_app):
        """Invalid IP address should raise InvalidIP."""
        with validation_app.test_request_context("/test", method="POST", json={"ip": "not.an.ip"}):
            with pytest.raises(InvalidIP):
                Validate.is_ip_addr()


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


class TestValidateSaveConfig:
    """Tests for Validate.save_config()."""

    def test_sets_default_false(self, validation_app):
        """Should set save_config to False if not provided."""
        with validation_app.test_request_context("/test", method="POST", json={}):
            from flask import request

            Validate.save_config()
            assert request.json["save_config"] is False

    def test_preserves_true_value(self, validation_app):
        """Should preserve save_config if set to True."""
        with validation_app.test_request_context("/test", method="POST", json={"save_config": True}):
            from flask import request

            Validate.save_config()
            assert request.json["save_config"] is True

    def test_non_bool_raises_error(self, validation_app):
        """Non-boolean save_config should raise UnprocessableEntity."""
        with validation_app.test_request_context("/test", method="POST", json={"save_config": "yes"}):
            with pytest.raises(UnprocessableEntity):
                Validate.save_config()


class TestValidateCommit:
    """Tests for Validate.commit()."""

    def test_sets_default_false(self, validation_app):
        """Should set commit to False if not provided."""
        with validation_app.test_request_context("/test", method="POST", json={}):
            from flask import request

            Validate.commit()
            assert request.json["commit"] is False

    def test_preserves_true_value(self, validation_app):
        """Should preserve commit if set to True."""
        with validation_app.test_request_context("/test", method="POST", json={"commit": True}):
            from flask import request

            Validate.commit()
            assert request.json["commit"] is True

    def test_non_bool_raises_error(self, validation_app):
        """Non-boolean commit should raise UnprocessableEntity."""
        with validation_app.test_request_context("/test", method="POST", json={"commit": 1}):
            with pytest.raises(UnprocessableEntity):
                Validate.commit()


class TestValidateIsCommandSet:
    """Tests for Validate.is_command_set()."""

    def test_valid_commands_list_passes(self, validation_app):
        """Valid commands list should pass."""
        with validation_app.test_request_context("/test", method="POST", json={"commands": ["show version"]}):
            Validate.is_command_set()  # Should not raise

    def test_missing_commands_raises_badrequest(self, validation_app):
        """Missing commands field should raise BadRequest."""
        with validation_app.test_request_context("/test", method="POST", json={}):
            with pytest.raises(BadRequest):
                Validate.is_command_set()

    def test_non_list_commands_raises_error(self, validation_app):
        """Non-list commands should raise UnprocessableEntity."""
        with validation_app.test_request_context("/test", method="POST", json={"commands": "show version"}):
            with pytest.raises(UnprocessableEntity):
                Validate.is_command_set()


class TestValidateHasPlatform:
    """Tests for Validate.has_platform()."""

    def test_sets_default_cisco_ios(self, validation_app):
        """Should set platform to cisco_ios if not provided."""
        with validation_app.test_request_context("/test", method="POST", json={}):
            from flask import request

            Validate.has_platform()
            assert request.json["platform"] == "cisco_ios"

    def test_preserves_existing_platform(self, validation_app):
        """Should preserve platform if already set."""
        with validation_app.test_request_context("/test", method="POST", json={"platform": "arista_eos"}):
            from flask import request

            Validate.has_platform()
            assert request.json["platform"] == "arista_eos"

    def test_non_string_raises_error(self, validation_app):
        """Non-string platform should raise UnprocessableEntity."""
        with validation_app.test_request_context("/test", method="POST", json={"platform": 123}):
            with pytest.raises(UnprocessableEntity):
                Validate.has_platform()


class TestValidateHasDelayFactor:
    """Tests for Validate.has_delay_factor()."""

    def test_sets_default_one(self, validation_app):
        """Should set delay_factor to 1 if not provided."""
        with validation_app.test_request_context("/test", method="POST", json={}):
            from flask import request

            Validate.has_delay_factor()
            assert request.json["delay_factor"] == 1

    def test_preserves_existing_delay_factor(self, validation_app):
        """Should preserve delay_factor if already set."""
        with validation_app.test_request_context("/test", method="POST", json={"delay_factor": 5}):
            from flask import request

            Validate.has_delay_factor()
            assert request.json["delay_factor"] == 5

    def test_non_int_raises_error(self, validation_app):
        """Non-integer delay_factor should raise UnprocessableEntity."""
        with validation_app.test_request_context("/test", method="POST", json={"delay_factor": "5"}):
            with pytest.raises(UnprocessableEntity):
                Validate.has_delay_factor()


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
