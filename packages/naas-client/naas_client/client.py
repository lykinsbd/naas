"""Synchronous NAAS client."""

from __future__ import annotations

from typing import Any

import httpx

from naas_client.exceptions import NaasApiError, NaasAuthError, NaasTimeoutError
from naas_client.job import Job
from naas_client.models import (
    ApiKeyCreateResponse,
    ApiKeyListItem,
    ApiKeyListResponse,
    ContextsResponse,
    FailedJobsResponse,
    HealthCheckResponse,
    JobResult,
    JobSubmission,
    ListJobsResponse,
)

_AUTH_ERROR_CODES = {401, 403}


class NaasClient:
    """Synchronous Python client for the NAAS v2 API.

    Args:
        base_url: NAAS server URL (e.g. "https://naas.example.com").
        username: Basic auth username (mutually exclusive with api_key).
        password: Basic auth password.
        api_key: JWT API key (mutually exclusive with username/password).
        verify: TLS certificate verification. Defaults to True.
        timeout: Request timeout in seconds. Defaults to 30.
        max_retries: Retries on transient failures (5xx, connection errors). Defaults to 3.
    """

    def __init__(
        self,
        base_url: str,
        *,
        username: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
        verify: bool = True,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries

        headers: dict[str, str] = {}
        auth: httpx.BasicAuth | None = None
        if api_key:
            headers["X-API-Key"] = api_key
        elif username and password:
            auth = httpx.BasicAuth(username, password)

        transport = httpx.HTTPTransport(retries=max_retries, verify=verify)
        self._client = httpx.Client(
            base_url=self._base_url,
            auth=auth,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        """Close the underlying HTTP connection."""
        self._client.close()

    def __enter__(self) -> NaasClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Make a request and handle errors."""
        try:
            resp = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise NaasTimeoutError(str(exc)) from exc

        if resp.status_code >= 400:
            cls = NaasAuthError if resp.status_code in _AUTH_ERROR_CODES else NaasApiError
            raise cls(resp.status_code, resp.reason_phrase or "Error", body=resp.text)

        return resp

    # -- Commands / Config ---------------------------------------------------

    def send_command(self, **kwargs: Any) -> Job:
        """Submit a send-command job. Returns a Job object for polling."""
        resp = self._request("POST", "/v2/send-command", json=kwargs)
        sub = JobSubmission.model_validate(resp.json())
        return Job(self, sub.job_id, "command")

    def send_command_structured(self, **kwargs: Any) -> Job:
        """Submit a structured send-command job (TextFSM/TTP parsing)."""
        resp = self._request("POST", "/v2/send-command-structured", json=kwargs)
        sub = JobSubmission.model_validate(resp.json())
        return Job(self, sub.job_id, "command")

    def send_config(self, **kwargs: Any) -> Job:
        """Submit a send-config job."""
        resp = self._request("POST", "/v2/send-config", json=kwargs)
        sub = JobSubmission.model_validate(resp.json())
        return Job(self, sub.job_id, "config")

    def get_command_result(self, job_id: str) -> JobResult:
        """Poll a send-command job result."""
        resp = self._request("GET", f"/v2/send-command/{job_id}")
        return JobResult.model_validate(resp.json())

    def get_config_result(self, job_id: str) -> JobResult:
        """Poll a send-config job result."""
        resp = self._request("GET", f"/v2/send-config/{job_id}")
        return JobResult.model_validate(resp.json())

    # -- Job management ------------------------------------------------------

    def list_jobs(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        status: str | None = None,
        tag: str | None = None,
    ) -> ListJobsResponse:
        """List jobs with pagination and optional filtering."""
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if status:
            params["status"] = status
        if tag:
            params["tag"] = tag
        resp = self._request("GET", "/v2/jobs", params=params)
        return ListJobsResponse.model_validate(resp.json())

    def cancel_job(self, job_id: str) -> None:
        """Cancel a queued or running job."""
        self._request("DELETE", f"/v2/jobs/{job_id}")

    def replay_job(self, job_id: str) -> JobSubmission:
        """Re-enqueue a failed job."""
        resp = self._request("POST", f"/v2/jobs/{job_id}/replay")
        return JobSubmission.model_validate(resp.json())

    def failed_jobs(self) -> FailedJobsResponse:
        """List jobs in the failed (dead letter) registry."""
        resp = self._request("GET", "/v2/jobs/failed")
        return FailedJobsResponse.model_validate(resp.json())

    # -- Contexts ------------------------------------------------------------

    def list_contexts(self) -> ContextsResponse:
        """List active routing contexts."""
        resp = self._request("GET", "/v2/contexts")
        return ContextsResponse.model_validate(resp.json())

    # -- API keys ------------------------------------------------------------

    def list_api_keys(self) -> list[ApiKeyListItem]:
        """List active API keys (metadata only)."""
        resp = self._request("GET", "/v2/api-keys")
        return ApiKeyListResponse.model_validate(resp.json()).keys

    def create_api_key(
        self,
        *,
        role: str = "admin",
        contexts: list[str] | None = None,
        ttl: int | None = None,
    ) -> ApiKeyCreateResponse:
        """Create a new API key. Returns the JWT token (shown once)."""
        payload: dict[str, Any] = {"role": role}
        if contexts is not None:
            payload["contexts"] = contexts
        if ttl is not None:
            payload["ttl"] = ttl
        resp = self._request("POST", "/v2/api-keys", json=payload)
        return ApiKeyCreateResponse.model_validate(resp.json())

    def delete_api_key(self, key_id: str) -> None:
        """Revoke an API key."""
        self._request("DELETE", f"/v2/api-keys/{key_id}")

    def rotate_api_key(self, key_id: str) -> ApiKeyCreateResponse:
        """Rotate an API key. Returns a new JWT token."""
        resp = self._request("POST", f"/v2/api-keys/{key_id}/rotate")
        return ApiKeyCreateResponse.model_validate(resp.json())

    # -- Health --------------------------------------------------------------

    def healthcheck(self) -> HealthCheckResponse:
        """Check NAAS server health."""
        resp = self._request("GET", "/healthcheck")
        return HealthCheckResponse.model_validate(resp.json())
