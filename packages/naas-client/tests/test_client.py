"""Tests for naas_client.client.NaasClient."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from naas_client.client import NaasClient
from naas_client.exceptions import NaasApiError, NaasAuthError, NaasTimeoutError
from naas_client.job import Job
from naas_client.models import (
    ApiKeyCreateResponse,
    ContextsResponse,
    FailedJobsResponse,
    HealthCheckResponse,
    JobResult,
    JobSubmission,
    ListJobsResponse,
)

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock

BASE = "https://naas.test"

JOB_SUBMISSION = {
    "job_id": "abc-123",
    "message": "Job enqueued",
    "queue_position": 1,
    "enqueued_at": "2026-04-09T12:00:00Z",
    "timeout": 300,
}

JOB_RESULT = {
    "job_id": "abc-123",
    "status": "finished",
    "results": {"show version": "Cisco IOS"},
}

HEALTH_RESPONSE = {
    "status": "healthy",
    "version": "2.0.0",
    "uptime_seconds": 0,
    "components": {
        "redis": {"status": "healthy"},
        "queue": {"status": "healthy", "depth": 0},
        "workers": {"status": "healthy", "count": 1, "active_jobs": 0},
        "failed_jobs": 0,
    },
}

API_KEY_RESPONSE = {
    "key_id": "k-1",
    "token": "eyJ...",
    "role": "admin",
    "contexts": ["*"],
    "expires_at": "2026-07-01T00:00:00Z",
}

API_KEY_LIST_ITEM = {
    "key_id": "k-1",
    "role": "admin",
    "contexts": ["*"],
    "created_at": "2026-01-01T00:00:00Z",
    "expires_at": "2026-07-01T00:00:00Z",
    "created_by": "admin",
}


class TestAuth:
    def test_basic_auth(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=HEALTH_RESPONSE)
        with NaasClient(BASE, username="admin", password="secret") as c:
            c.healthcheck()
        req = httpx_mock.get_requests()[0]
        assert req.headers.get("authorization", "").startswith("Basic ")

    def test_api_key_auth(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=HEALTH_RESPONSE)
        with NaasClient(BASE, api_key="my-jwt") as c:
            c.healthcheck()
        req = httpx_mock.get_requests()[0]
        assert req.headers["x-api-key"] == "my-jwt"


class TestErrorHandling:
    def test_401_raises_auth_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=401, text="Unauthorized")
        with NaasClient(BASE, username="x", password="x") as c, pytest.raises(NaasAuthError) as exc_info:
            c.healthcheck()
        assert exc_info.value.status_code == 401

    def test_403_raises_auth_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=403, text="Forbidden")
        with NaasClient(BASE, username="x", password="x") as c, pytest.raises(NaasAuthError):
            c.healthcheck()

    def test_500_raises_api_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=500, text="Internal Server Error")
        with NaasClient(BASE, username="x", password="x") as c, pytest.raises(NaasApiError) as exc_info:
            c.healthcheck()
        assert exc_info.value.status_code == 500
        assert exc_info.value.body == "Internal Server Error"

    def test_timeout_raises_timeout_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_exception(httpx.ReadTimeout("timed out"))
        with NaasClient(BASE, username="x", password="x") as c, pytest.raises(NaasTimeoutError):
            c.healthcheck()


class TestCommands:
    def test_send_command(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=202, json=JOB_SUBMISSION)
        with NaasClient(BASE, username="x", password="x") as c:
            result = c.send_command(host="10.0.0.1", platform="cisco_ios", commands=["show version"])
        assert isinstance(result, Job)
        assert result.job_id == "abc-123"
        assert httpx_mock.get_requests()[0].url.path == "/v2/send-command"

    def test_send_command_structured(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=202, json=JOB_SUBMISSION)
        with NaasClient(BASE, username="x", password="x") as c:
            result = c.send_command_structured(host="10.0.0.1", commands=["show version"])
        assert isinstance(result, Job)
        assert httpx_mock.get_requests()[0].url.path == "/v2/send-command-structured"

    def test_send_config(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=202, json=JOB_SUBMISSION)
        with NaasClient(BASE, username="x", password="x") as c:
            result = c.send_config(host="10.0.0.1", config=["interface Gi0/1", "shutdown"])
        assert isinstance(result, Job)
        assert httpx_mock.get_requests()[0].url.path == "/v2/send-config"

    def test_get_command_result(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=JOB_RESULT)
        with NaasClient(BASE, username="x", password="x") as c:
            result = c.get_command_result("abc-123")
        assert isinstance(result, JobResult)
        assert result.status == "finished"
        assert httpx_mock.get_requests()[0].url.path == "/v2/send-command/abc-123"

    def test_get_config_result(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=JOB_RESULT)
        with NaasClient(BASE, username="x", password="x") as c:
            c.get_config_result("abc-123")
        assert httpx_mock.get_requests()[0].url.path == "/v2/send-config/abc-123"


class TestJobManagement:
    def test_list_jobs(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"jobs": [], "pagination": {"page": 1, "per_page": 20, "total": 0, "pages": 0}})
        with NaasClient(BASE, username="x", password="x") as c:
            result = c.list_jobs()
        assert isinstance(result, ListJobsResponse)

    def test_list_jobs_with_filters(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"jobs": [], "pagination": {"page": 2, "per_page": 10, "total": 0, "pages": 0}})
        with NaasClient(BASE, username="x", password="x") as c:
            c.list_jobs(page=2, per_page=10, status="failed", tag="env:prod")
        params = httpx_mock.get_requests()[0].url.params
        assert params["page"] == "2"
        assert params["status"] == "failed"
        assert params["tag"] == "env:prod"

    def test_cancel_job(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=204)
        with NaasClient(BASE, username="x", password="x") as c:
            c.cancel_job("abc-123")
        assert httpx_mock.get_requests()[0].method == "DELETE"
        assert httpx_mock.get_requests()[0].url.path == "/v2/jobs/abc-123"

    def test_replay_job(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=202, json=JOB_SUBMISSION)
        with NaasClient(BASE, username="x", password="x") as c:
            result = c.replay_job("abc-123")
        assert isinstance(result, JobSubmission)
        assert httpx_mock.get_requests()[0].url.path == "/v2/jobs/abc-123/replay"

    def test_failed_jobs(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"jobs": [], "total": 0})
        with NaasClient(BASE, username="x", password="x") as c:
            result = c.failed_jobs()
        assert isinstance(result, FailedJobsResponse)


class TestContexts:
    def test_list_contexts(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"contexts": [{"name": "default", "workers": 4, "queue_depth": 0}]})
        with NaasClient(BASE, username="x", password="x") as c:
            result = c.list_contexts()
        assert isinstance(result, ContextsResponse)
        assert result.contexts[0].name == "default"


class TestApiKeys:
    def test_list_api_keys(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"keys": [API_KEY_LIST_ITEM]})
        with NaasClient(BASE, username="x", password="x") as c:
            keys = c.list_api_keys()
        assert len(keys) == 1
        assert keys[0].key_id == "k-1"

    def test_create_api_key(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=201, json={**API_KEY_RESPONSE, "role": "operator", "contexts": ["default"]})
        with NaasClient(BASE, username="x", password="x") as c:
            result = c.create_api_key(role="operator", contexts=["default"], ttl=3600)
        assert isinstance(result, ApiKeyCreateResponse)
        payload = json.loads(httpx_mock.get_requests()[0].read())
        assert payload["role"] == "operator"
        assert payload["contexts"] == ["default"]
        assert payload["ttl"] == 3600

    def test_create_api_key_defaults(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=201, json=API_KEY_RESPONSE)
        with NaasClient(BASE, username="x", password="x") as c:
            c.create_api_key()
        payload = json.loads(httpx_mock.get_requests()[0].read())
        assert payload == {"role": "admin"}

    def test_delete_api_key(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=204)
        with NaasClient(BASE, username="x", password="x") as c:
            c.delete_api_key("k-1")
        assert httpx_mock.get_requests()[0].method == "DELETE"

    def test_rotate_api_key(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=201, json={**API_KEY_RESPONSE, "token": "new-jwt"})
        with NaasClient(BASE, username="x", password="x") as c:
            result = c.rotate_api_key("k-1")
        assert result.token == "new-jwt"


class TestHealthcheck:
    def test_healthcheck(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=HEALTH_RESPONSE)
        with NaasClient(BASE, username="x", password="x") as c:
            result = c.healthcheck()
        assert isinstance(result, HealthCheckResponse)
        assert result.status == "healthy"


class TestContextManager:
    def test_close(self) -> None:
        c = NaasClient(BASE, username="x", password="x")
        c.close()

    def test_trailing_slash_stripped(self) -> None:
        c = NaasClient("https://naas.test/", username="x", password="x")
        assert c._base_url == "https://naas.test"
        c.close()
