"""Asynchronous NAAS client."""

from __future__ import annotations

from typing import Any

import httpx

from naas_client.async_job import AsyncJob
from naas_client.exceptions import NaasApiError, NaasAuthError, NaasTimeoutError
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


class AsyncNaasClient:
    """Asynchronous Python client for the NAAS v2 API.

    Args:
        base_url: NAAS server URL.
        username: Basic auth username (mutually exclusive with api_key).
        password: Basic auth password.
        api_key: JWT API key (mutually exclusive with username/password).
        verify: TLS certificate verification. Defaults to True.
        timeout: Request timeout in seconds. Defaults to 30.
        max_retries: Retries on transient failures. Defaults to 3.
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

        headers: dict[str, str] = {}
        auth: httpx.BasicAuth | None = None
        if api_key:
            headers["X-API-Key"] = api_key
        elif username and password:
            auth = httpx.BasicAuth(username, password)

        transport = httpx.AsyncHTTPTransport(retries=max_retries)
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            auth=auth,
            headers=headers,
            verify=verify,
            timeout=timeout,
            transport=transport,
        )

    async def close(self) -> None:
        """Close the underlying HTTP connection."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncNaasClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            resp = await self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise NaasTimeoutError(str(exc)) from exc

        if resp.status_code >= 400:
            cls = NaasAuthError if resp.status_code in _AUTH_ERROR_CODES else NaasApiError
            raise cls(resp.status_code, resp.reason_phrase or "Error", body=resp.text)

        return resp

    # -- Commands / Config ---------------------------------------------------

    async def send_command(self, **kwargs: Any) -> AsyncJob:
        resp = await self._request("POST", "/v2/send-command", json=kwargs)
        sub = JobSubmission.model_validate(resp.json())
        return AsyncJob(self, sub.job_id, "command")

    async def send_command_structured(self, **kwargs: Any) -> AsyncJob:
        resp = await self._request("POST", "/v2/send-command-structured", json=kwargs)
        sub = JobSubmission.model_validate(resp.json())
        return AsyncJob(self, sub.job_id, "command")

    async def send_config(self, **kwargs: Any) -> AsyncJob:
        resp = await self._request("POST", "/v2/send-config", json=kwargs)
        sub = JobSubmission.model_validate(resp.json())
        return AsyncJob(self, sub.job_id, "config")

    async def get_command_result(self, job_id: str) -> JobResult:
        resp = await self._request("GET", f"/v2/send-command/{job_id}")
        return JobResult.model_validate(resp.json())

    async def get_config_result(self, job_id: str) -> JobResult:
        resp = await self._request("GET", f"/v2/send-config/{job_id}")
        return JobResult.model_validate(resp.json())

    # -- Job management ------------------------------------------------------

    async def list_jobs(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        status: str | None = None,
        tag: str | None = None,
    ) -> ListJobsResponse:
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if status:
            params["status"] = status
        if tag:
            params["tag"] = tag
        resp = await self._request("GET", "/v2/jobs", params=params)
        return ListJobsResponse.model_validate(resp.json())

    async def cancel_job(self, job_id: str) -> None:
        await self._request("DELETE", f"/v2/jobs/{job_id}")

    async def replay_job(self, job_id: str) -> JobSubmission:
        resp = await self._request("POST", f"/v2/jobs/{job_id}/replay")
        return JobSubmission.model_validate(resp.json())

    async def failed_jobs(self) -> FailedJobsResponse:
        resp = await self._request("GET", "/v2/jobs/failed")
        return FailedJobsResponse.model_validate(resp.json())

    # -- Contexts ------------------------------------------------------------

    async def list_contexts(self) -> ContextsResponse:
        resp = await self._request("GET", "/v2/contexts")
        return ContextsResponse.model_validate(resp.json())

    # -- API keys ------------------------------------------------------------

    async def list_api_keys(self) -> list[ApiKeyListItem]:
        resp = await self._request("GET", "/v2/api-keys")
        return ApiKeyListResponse.model_validate(resp.json()).keys

    async def create_api_key(
        self,
        *,
        role: str = "admin",
        contexts: list[str] | None = None,
        ttl: int | None = None,
    ) -> ApiKeyCreateResponse:
        payload: dict[str, Any] = {"role": role}
        if contexts is not None:
            payload["contexts"] = contexts
        if ttl is not None:
            payload["ttl"] = ttl
        resp = await self._request("POST", "/v2/api-keys", json=payload)
        return ApiKeyCreateResponse.model_validate(resp.json())

    async def delete_api_key(self, key_id: str) -> None:
        await self._request("DELETE", f"/v2/api-keys/{key_id}")

    async def rotate_api_key(self, key_id: str) -> ApiKeyCreateResponse:
        resp = await self._request("POST", f"/v2/api-keys/{key_id}/rotate")
        return ApiKeyCreateResponse.model_validate(resp.json())

    # -- Health --------------------------------------------------------------

    async def healthcheck(self) -> HealthCheckResponse:
        resp = await self._request("GET", "/healthcheck")
        return HealthCheckResponse.model_validate(resp.json())
