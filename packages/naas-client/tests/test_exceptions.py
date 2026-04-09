"""Tests for naas_client.exceptions."""

import pytest

from naas_client.exceptions import (
    NaasApiError,
    NaasAuthError,
    NaasError,
    NaasJobError,
    NaasTimeoutError,
)


class TestExceptionHierarchy:
    """All exceptions inherit from NaasError."""

    def test_naas_error_is_base(self) -> None:
        assert issubclass(NaasApiError, NaasError)
        assert issubclass(NaasAuthError, NaasError)
        assert issubclass(NaasTimeoutError, NaasError)
        assert issubclass(NaasJobError, NaasError)

    def test_auth_error_is_api_error(self) -> None:
        assert issubclass(NaasAuthError, NaasApiError)


class TestNaasApiError:
    def test_attributes(self) -> None:
        err = NaasApiError(500, "Internal Server Error", body='{"detail": "oops"}')
        assert err.status_code == 500
        assert err.body == '{"detail": "oops"}'
        assert "HTTP 500" in str(err)

    def test_default_body(self) -> None:
        err = NaasApiError(404, "Not Found")
        assert err.body == ""

    def test_catchable_as_naas_error(self) -> None:
        with pytest.raises(NaasError):
            raise NaasApiError(400, "Bad Request")


class TestNaasAuthError:
    def test_inherits_api_error_attrs(self) -> None:
        err = NaasAuthError(401, "Unauthorized")
        assert err.status_code == 401

    def test_catchable_as_api_error(self) -> None:
        with pytest.raises(NaasApiError):
            raise NaasAuthError(403, "Forbidden")


class TestNaasTimeoutError:
    def test_message(self) -> None:
        err = NaasTimeoutError("Request timed out after 30s")
        assert "30s" in str(err)

    def test_catchable_as_naas_error(self) -> None:
        with pytest.raises(NaasError):
            raise NaasTimeoutError("timeout")


class TestNaasJobError:
    def test_attributes(self) -> None:
        err = NaasJobError("abc-123", "Connection refused")
        assert err.job_id == "abc-123"
        assert err.error == "Connection refused"
        assert "abc-123" in str(err)
        assert "Connection refused" in str(err)

    def test_catchable_as_naas_error(self) -> None:
        with pytest.raises(NaasError):
            raise NaasJobError("x", "fail")
