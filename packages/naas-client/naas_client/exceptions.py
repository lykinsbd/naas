"""Exception hierarchy for naas-client."""

from __future__ import annotations


class NaasError(Exception):
    """Base exception for all naas-client errors."""


class NaasApiError(NaasError):
    """Non-2xx response from the NAAS API."""

    def __init__(self, status_code: int, message: str, body: str = "") -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {message}")


class NaasAuthError(NaasApiError):
    """Authentication or authorization failure (401/403)."""


class NaasTimeoutError(NaasError):
    """Request timeout or job wait timeout."""


class NaasJobError(NaasError):
    """Job completed with failed status."""

    def __init__(
        self,
        job_id: str,
        error: str,
        *,
        error_code: str | None = None,
        error_retryable: bool | None = None,
    ) -> None:
        self.job_id = job_id
        self.error = error
        self.error_code = error_code
        self.error_retryable = error_retryable
        super().__init__(f"Job {job_id} failed: {error}")


class NaasConnectionError(NaasJobError):
    """CONNECTION_TIMEOUT or SSH_ERROR — device unreachable."""


class NaasDeviceAuthError(NaasJobError):
    """AUTH_FAILURE — device rejected credentials."""


class NaasConfigError(NaasJobError):
    """CONFIG_REJECTED — device rejected configuration commands."""


class NaasCircuitOpenError(NaasJobError):
    """CIRCUIT_OPEN — too many recent failures to this device."""


#: Maps error_code to the appropriate exception subclass.
_ERROR_CODE_MAP: dict[str, type[NaasJobError]] = {
    "CONNECTION_TIMEOUT": NaasConnectionError,
    "SSH_ERROR": NaasConnectionError,
    "AUTH_FAILURE": NaasDeviceAuthError,
    "CONFIG_REJECTED": NaasConfigError,
    "CIRCUIT_OPEN": NaasCircuitOpenError,
}


def _job_error_from_result(
    job_id: str,
    error: str | None,
    error_code: str | None = None,
    error_retryable: bool | None = None,
) -> NaasJobError:
    """Create the most specific NaasJobError subclass for the given error code."""
    cls = _ERROR_CODE_MAP.get(error_code or "", NaasJobError)
    return cls(job_id, error or "Unknown error", error_code=error_code, error_retryable=error_retryable)
