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

    def __init__(self, job_id: str, error: str) -> None:
        self.job_id = job_id
        self.error = error
        super().__init__(f"Job {job_id} failed: {error}")
