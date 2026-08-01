"""Tests for AsyncNaasClient and AsyncJob."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from naas_client.async_client import AsyncNaasClient
from naas_client.async_job import AsyncJob
from naas_client.exceptions import NaasApiError, NaasAuthError, NaasJobError, NaasTimeoutError
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

JOB_RESULT = {"job_id": "abc-123", "status": "finished", "results": {"show version": "Cisco IOS"}}

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


class TestAsyncAuth:
    @pytest.mark.asyncio
    async def test_basic_auth(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=HEALTH_RESPONSE)
        async with AsyncNaasClient(BASE, username="admin", password="secret") as c:
            await c.healthcheck()
        assert httpx_mock.get_requests()[0].headers.get("authorization", "").startswith("Basic ")

    @pytest.mark.asyncio
    async def test_api_key_auth(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=HEALTH_RESPONSE)
        async with AsyncNaasClient(BASE, api_key="my-jwt") as c:
            await c.healthcheck()
        assert httpx_mock.get_requests()[0].headers["x-api-key"] == "my-jwt"


class TestAsyncErrors:
    @pytest.mark.asyncio
    async def test_401(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=401, text="Unauthorized")
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            with pytest.raises(NaasAuthError):
                await c.healthcheck()

    @pytest.mark.asyncio
    async def test_500(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=500, text="ISE")
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            with pytest.raises(NaasApiError):
                await c.healthcheck()

    @pytest.mark.asyncio
    async def test_timeout(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_exception(httpx.ReadTimeout("timed out"))
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            with pytest.raises(NaasTimeoutError):
                await c.healthcheck()


class TestAsyncCommands:
    @pytest.mark.asyncio
    async def test_send_command(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=202, json=JOB_SUBMISSION)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            job = await c.send_command(host="10.0.0.1", commands=["show version"])
        assert isinstance(job, AsyncJob)
        assert job.job_id == "abc-123"

    @pytest.mark.asyncio
    async def test_send_command_structured(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=202, json=JOB_SUBMISSION)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            job = await c.send_command_structured(host="10.0.0.1", commands=["show version"])
        assert isinstance(job, AsyncJob)

    @pytest.mark.asyncio
    async def test_send_config(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=202, json=JOB_SUBMISSION)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            job = await c.send_config(host="10.0.0.1", config=["interface Gi0/1"])
        assert isinstance(job, AsyncJob)

    @pytest.mark.asyncio
    async def test_get_command_result(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=JOB_RESULT)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            result = await c.get_command_result("abc-123")
        assert isinstance(result, JobResult)

    @pytest.mark.asyncio
    async def test_get_config_result(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=JOB_RESULT)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            await c.get_config_result("abc-123")
        assert httpx_mock.get_requests()[0].url.path == "/v2/send-config/abc-123"


class TestAsyncJobManagement:
    @pytest.mark.asyncio
    async def test_list_jobs(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"jobs": [], "pagination": {"page": 1, "per_page": 20, "total": 0, "pages": 0}})
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            result = await c.list_jobs()
        assert isinstance(result, ListJobsResponse)

    @pytest.mark.asyncio
    async def test_list_jobs_with_filters(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"jobs": [], "pagination": {"page": 2, "per_page": 10, "total": 0, "pages": 0}})
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            await c.list_jobs(page=2, per_page=10, status="failed", tag="env:prod")
        params = httpx_mock.get_requests()[0].url.params
        assert params["status"] == "failed"

    @pytest.mark.asyncio
    async def test_cancel_job(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=204)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            await c.cancel_job("abc-123")

    @pytest.mark.asyncio
    async def test_replay_job(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=202, json=JOB_SUBMISSION)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            result = await c.replay_job("abc-123")
        assert isinstance(result, JobSubmission)

    @pytest.mark.asyncio
    async def test_failed_jobs(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"jobs": [], "total": 0})
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            result = await c.failed_jobs()
        assert isinstance(result, FailedJobsResponse)


class TestAsyncContextsAndKeys:
    @pytest.mark.asyncio
    async def test_list_contexts(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"contexts": [{"name": "default", "workers": 4, "queue_depth": 0}]})
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            result = await c.list_contexts()
        assert isinstance(result, ContextsResponse)

    @pytest.mark.asyncio
    async def test_list_api_keys(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"keys": [API_KEY_LIST_ITEM]})
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            keys = await c.list_api_keys()
        assert len(keys) == 1

    @pytest.mark.asyncio
    async def test_create_api_key(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=201, json=API_KEY_RESPONSE)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            result = await c.create_api_key(role="admin", contexts=["*"], ttl=3600)
        assert isinstance(result, ApiKeyCreateResponse)
        payload = json.loads(httpx_mock.get_requests()[0].read())
        assert payload["ttl"] == 3600

    @pytest.mark.asyncio
    async def test_create_api_key_defaults(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=201, json=API_KEY_RESPONSE)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            await c.create_api_key()
        payload = json.loads(httpx_mock.get_requests()[0].read())
        assert payload == {"role": "admin"}

    @pytest.mark.asyncio
    async def test_delete_api_key(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=204)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            await c.delete_api_key("k-1")

    @pytest.mark.asyncio
    async def test_rotate_api_key(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=201, json={**API_KEY_RESPONSE, "token": "new"})
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            result = await c.rotate_api_key("k-1")
        assert result.token == "new"

    @pytest.mark.asyncio
    async def test_healthcheck(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=HEALTH_RESPONSE)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            result = await c.healthcheck()
        assert isinstance(result, HealthCheckResponse)


class TestAsyncJob:
    @pytest.mark.asyncio
    async def test_poll_command(self) -> None:
        client = AsyncMock()
        client.get_command_result.return_value = JobResult.model_validate(JOB_RESULT)
        job = AsyncJob(client, "abc-123", "command")
        result = await job.poll()
        assert result.status == "finished"

    @pytest.mark.asyncio
    async def test_poll_config(self) -> None:
        client = AsyncMock()
        client.get_config_result.return_value = JobResult.model_validate(JOB_RESULT)
        job = AsyncJob(client, "abc-123", "config")
        await job.poll()
        client.get_config_result.assert_called_once_with("abc-123")

    @pytest.mark.asyncio
    @patch("naas_client.async_job.asyncio.sleep", new_callable=AsyncMock)
    @patch("naas_client.async_job.asyncio.get_event_loop")
    async def test_wait_returns_on_finished(self, mock_loop: AsyncMock, mock_sleep: AsyncMock) -> None:
        mock_loop.return_value.time.side_effect = [0.0, 0.5]
        client = AsyncMock()
        client.get_command_result.return_value = JobResult.model_validate(JOB_RESULT)
        job = AsyncJob(client, "abc-123", "command")
        result = await job.wait(timeout=10)
        assert result.status == "finished"

    @pytest.mark.asyncio
    @patch("naas_client.async_job.asyncio.sleep", new_callable=AsyncMock)
    @patch("naas_client.async_job.asyncio.get_event_loop")
    async def test_wait_raises_on_failure(self, mock_loop: AsyncMock, mock_sleep: AsyncMock) -> None:
        mock_loop.return_value.time.side_effect = [0.0, 0.5]
        client = AsyncMock()
        client.get_command_result.return_value = JobResult.model_validate(
            {"job_id": "abc-123", "status": "failed", "error": "Connection refused"}
        )
        job = AsyncJob(client, "abc-123", "command")
        with pytest.raises(NaasJobError):
            await job.wait(timeout=10)

    @pytest.mark.asyncio
    @patch("naas_client.async_job.asyncio.sleep", new_callable=AsyncMock)
    @patch("naas_client.async_job.asyncio.get_event_loop")
    async def test_wait_raises_on_failure_no_msg(self, mock_loop: AsyncMock, mock_sleep: AsyncMock) -> None:
        mock_loop.return_value.time.side_effect = [0.0, 0.5]
        client = AsyncMock()
        client.get_command_result.return_value = JobResult.model_validate({"job_id": "abc-123", "status": "failed"})
        job = AsyncJob(client, "abc-123", "command")
        with pytest.raises(NaasJobError, match="Unknown error"):
            await job.wait(timeout=10)

    @pytest.mark.asyncio
    @patch("naas_client.async_job.asyncio.sleep", new_callable=AsyncMock)
    @patch("naas_client.async_job.asyncio.get_event_loop")
    async def test_wait_timeout(self, mock_loop: AsyncMock, mock_sleep: AsyncMock) -> None:
        mock_loop.return_value.time.side_effect = [0.0, 5.0, 11.0]
        client = AsyncMock()
        client.get_command_result.return_value = JobResult.model_validate({"job_id": "abc-123", "status": "queued"})
        job = AsyncJob(client, "abc-123", "command")
        with pytest.raises(NaasTimeoutError):
            await job.wait(timeout=10)

    @pytest.mark.asyncio
    async def test_properties(self) -> None:
        job = AsyncJob(AsyncMock(), "abc-123", "command")
        assert job.is_complete is False
        assert job.is_failed is False
        assert job.result is None

    @pytest.mark.asyncio
    async def test_cancel(self) -> None:
        client = AsyncMock()
        job = AsyncJob(client, "abc-123", "command")
        await job.cancel()
        client.cancel_job.assert_called_once_with("abc-123")

    @pytest.mark.asyncio
    async def test_replay(self) -> None:
        client = AsyncMock()
        client.replay_job.return_value = JobSubmission.model_validate(JOB_SUBMISSION)
        job = AsyncJob(client, "abc-123", "command")
        new_job = await job.replay()
        assert isinstance(new_job, AsyncJob)
        assert new_job.job_id == "abc-123"


class TestAsyncContextManager:
    @pytest.mark.asyncio
    async def test_close(self) -> None:
        c = AsyncNaasClient(BASE, username="x", password="x")
        await c.close()

    def test_trailing_slash_stripped(self) -> None:
        c = AsyncNaasClient("https://naas.test/", username="x", password="x")
        assert c._base_url == "https://naas.test"

    # -- Batch operations tests --

    @pytest.mark.asyncio
    async def test_send_command_batch(self, httpx_mock: HTTPXMock) -> None:
        batch_resp = {"batch_id": "batch-abc123", "job_ids": ["j1", "j2"], "total": 2}
        httpx_mock.add_response(status_code=202, json=batch_resp)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            result = await c.send_command_batch(
                devices=[{"host": "10.0.0.1", "platform": "cisco_ios"}],
                commands=["show version"],
            )
        assert result.batch_id == "batch-abc123"
        assert result.total == 2

    @pytest.mark.asyncio
    async def test_send_config_batch(self, httpx_mock: HTTPXMock) -> None:
        batch_resp = {"batch_id": "batch-def456", "job_ids": ["j1"], "total": 1}
        httpx_mock.add_response(status_code=202, json=batch_resp)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            result = await c.send_config_batch(
                devices=[{"host": "10.0.0.1", "platform": "cisco_ios"}],
                commands=["interface Gi0/1"],
            )
        assert result.batch_id == "batch-def456"

    @pytest.mark.asyncio
    async def test_get_batch(self, httpx_mock: HTTPXMock) -> None:
        status_resp = {
            "batch_id": "batch-abc123",
            "total": 2,
            "completed": 2,
            "pending": 0,
            "failed": 0,
            "jobs": [
                {"job_id": "j1", "host": "10.0.0.1", "status": "finished"},
                {"job_id": "j2", "host": "10.0.0.2", "status": "finished"},
            ],
        }
        httpx_mock.add_response(status_code=200, json=status_resp)
        async with AsyncNaasClient(BASE, username="x", password="x") as c:
            result = await c.get_batch("batch-abc123")
        assert result.batch_id == "batch-abc123"
        assert result.completed == 2
