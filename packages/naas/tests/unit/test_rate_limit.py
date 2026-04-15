"""Tests for naas.library.rate_limit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fakeredis import FakeStrictRedis

from naas.library.rate_limit import (
    _check_limit,
    _get_caller_id,
    _is_exempt,
    check_rate_limit,
    rate_limited,
)


@pytest.fixture()
def redis():
    return FakeStrictRedis()


class TestCheckLimit:
    def test_allows_under_limit(self, redis):
        count, remaining = _check_limit("k", 5, 60, redis)
        assert count == 1
        assert remaining == 4

    def test_tracks_multiple_requests(self, redis):
        for _ in range(4):
            _check_limit("k", 5, 60, redis)
        count, remaining = _check_limit("k", 5, 60, redis)
        assert count == 5
        assert remaining == 0

    def test_exceeds_limit(self, redis):
        for _ in range(5):
            _check_limit("k", 5, 60, redis)
        count, remaining = _check_limit("k", 5, 60, redis)
        assert count == 6
        assert remaining == 0

    def test_window_expiry(self, redis):
        """Old entries outside the window are pruned."""
        with patch("naas.library.rate_limit.time") as mock_time:
            mock_time.time.return_value = 1000.0
            for _ in range(5):
                _check_limit("k", 5, 60, redis)

            # Advance past window
            mock_time.time.return_value = 1061.0
            count, remaining = _check_limit("k", 5, 60, redis)
            assert count == 1
            assert remaining == 4


class TestCheckRateLimit:
    def test_per_caller_allows(self, redis):
        with (
            patch("naas.library.rate_limit.RATE_LIMIT_PER_CALLER", 5),
            patch("naas.library.rate_limit.RATE_LIMIT_WINDOW", 60),
            patch("naas.library.rate_limit.g") as mock_g,
        ):
            result = check_rate_limit("user1", None, redis)
            assert result is None
            assert mock_g.rate_limit_remaining == 4

    def test_per_caller_exceeds(self, redis):
        with (
            patch("naas.library.rate_limit.RATE_LIMIT_PER_CALLER", 3),
            patch("naas.library.rate_limit.RATE_LIMIT_WINDOW", 60),
            patch("naas.library.rate_limit.g"),
        ):
            for _ in range(3):
                check_rate_limit("user1", None, redis)
            result = check_rate_limit("user1", None, redis)
            assert result is not None
            assert result["error"] == "Rate limit exceeded"

    def test_per_device_exceeds(self, redis):
        with (
            patch("naas.library.rate_limit.RATE_LIMIT_PER_CALLER", 1000),
            patch("naas.library.rate_limit.RATE_LIMIT_PER_CALLER_DEVICE", 2),
            patch("naas.library.rate_limit.RATE_LIMIT_WINDOW", 60),
            patch("naas.library.rate_limit.g"),
        ):
            for _ in range(2):
                check_rate_limit("user1", "10.0.0.1", redis)
            result = check_rate_limit("user1", "10.0.0.1", redis)
            assert result is not None
            assert result["error"] == "Rate limit exceeded"

    def test_per_device_independent(self, redis):
        """Different devices have independent limits."""
        with (
            patch("naas.library.rate_limit.RATE_LIMIT_PER_CALLER", 1000),
            patch("naas.library.rate_limit.RATE_LIMIT_PER_CALLER_DEVICE", 2),
            patch("naas.library.rate_limit.RATE_LIMIT_WINDOW", 60),
            patch("naas.library.rate_limit.g"),
        ):
            for _ in range(2):
                check_rate_limit("user1", "10.0.0.1", redis)
            # Different device — should be allowed
            result = check_rate_limit("user1", "10.0.0.2", redis)
            assert result is None

    def test_different_callers_independent(self, redis):
        with (
            patch("naas.library.rate_limit.RATE_LIMIT_PER_CALLER", 2),
            patch("naas.library.rate_limit.RATE_LIMIT_WINDOW", 60),
            patch("naas.library.rate_limit.g"),
        ):
            for _ in range(2):
                check_rate_limit("user1", None, redis)
            # Different caller — should be allowed
            result = check_rate_limit("user2", None, redis)
            assert result is None


class TestGetCallerId:
    def test_bearer_auth(self):
        with patch("naas.library.rate_limit.g") as mock_g:
            mock_g.auth_method = "bearer"
            mock_g.jwt_claims = {"sub": "api-key-123"}
            assert _get_caller_id() == "api-key-123"

    def test_basic_auth(self):
        with patch("naas.library.rate_limit.g") as mock_g:
            mock_g.auth_method = "basic"
            mock_g.credentials = MagicMock(username="admin")
            assert _get_caller_id() == "admin"

    def test_fallback_to_ip(self):
        with patch("naas.library.rate_limit.g") as mock_g, patch("naas.library.rate_limit.request") as mock_req:
            del mock_g.auth_method
            del mock_g.credentials
            mock_req.remote_addr = "192.168.1.1"
            assert _get_caller_id() == "192.168.1.1"


class TestIsExempt:
    def test_basic_auth_exempt(self):
        with patch("naas.library.rate_limit.g") as mock_g:
            mock_g.auth_method = "basic"
            assert _is_exempt() is True

    def test_admin_role_exempt(self):
        with (
            patch("naas.library.rate_limit.g") as mock_g,
            patch("naas.library.rate_limit.RATE_LIMIT_EXEMPT_ROLES", frozenset({"admin"})),
        ):
            mock_g.auth_method = "bearer"
            mock_g.jwt_claims = {"role": "admin"}
            assert _is_exempt() is True

    def test_operator_not_exempt(self):
        with (
            patch("naas.library.rate_limit.g") as mock_g,
            patch("naas.library.rate_limit.RATE_LIMIT_EXEMPT_ROLES", frozenset({"admin"})),
        ):
            mock_g.auth_method = "bearer"
            mock_g.jwt_claims = {"role": "operator"}
            assert _is_exempt() is False


class TestRateLimitedDecorator:
    def test_disabled_skips_check(self):
        @rate_limited
        def dummy():
            return "ok"

        with patch("naas.library.rate_limit.RATE_LIMIT_ENABLED", False):
            assert dummy() == "ok"

    def test_exempt_skips_check(self):
        @rate_limited
        def dummy():
            return "ok"

        with (
            patch("naas.library.rate_limit.RATE_LIMIT_ENABLED", True),
            patch("naas.library.rate_limit._is_exempt", return_value=True),
        ):
            assert dummy() == "ok"

    def test_enforces_limit(self, app):
        @rate_limited
        def dummy():
            return "ok"

        with app.test_request_context(json={"host": "10.0.0.1"}):
            with (
                patch("naas.library.rate_limit.RATE_LIMIT_ENABLED", True),
                patch("naas.library.rate_limit._is_exempt", return_value=False),
                patch("naas.library.rate_limit.check_rate_limit") as mock_check,
                patch("naas.library.rate_limit._get_caller_id", return_value="testuser"),
            ):
                mock_check.return_value = None
                dummy()
                mock_check.assert_called_once()

    def test_returns_429_on_limit(self, app):
        @rate_limited
        def dummy():
            return "ok"

        with app.test_request_context(json={"host": "10.0.0.1"}):
            with (
                patch("naas.library.rate_limit.RATE_LIMIT_ENABLED", True),
                patch("naas.library.rate_limit._is_exempt", return_value=False),
                patch(
                    "naas.library.rate_limit.check_rate_limit",
                    return_value={"error": "Rate limit exceeded", "retry_after": 60},
                ),
                patch("naas.library.rate_limit._get_caller_id", return_value="testuser"),
            ):
                body, status, headers = dummy()
                assert status == 429
                assert headers["Retry-After"] == "60"
                assert body["error"] == "Rate limit exceeded"
