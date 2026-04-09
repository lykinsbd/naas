"""Integration tests for NaasClient against a running NAAS server."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from naas_client.client import NaasClient
from naas_client.exceptions import NaasApiError, NaasAuthError
from naas_client.models import HealthCheckResponse, JobStatus

if TYPE_CHECKING:
    from naas_client.async_client import AsyncNaasClient


class TestHealthcheck:
    def test_healthcheck(self, client: NaasClient) -> None:
        health = client.healthcheck()
        assert isinstance(health, HealthCheckResponse)
        assert health.status == "healthy"
        assert health.components.workers.count is not None
        assert health.components.workers.count > 0


class TestAuth:
    def test_bad_api_key_rejected(self) -> None:
        c = NaasClient("https://localhost:18443", api_key="invalid-jwt", verify=False)
        with pytest.raises(NaasAuthError):
            c.list_jobs()
        c.close()


class TestContexts:
    def test_list_contexts(self, client: NaasClient) -> None:
        result = client.list_contexts()
        assert len(result.contexts) >= 1
        names = [c.name for c in result.contexts]
        assert "default" in names


class TestJobs:
    def test_list_jobs(self, client: NaasClient) -> None:
        result = client.list_jobs()
        assert result.pagination.page == 1

    def test_cancel_nonexistent_job(self, client: NaasClient) -> None:
        with pytest.raises(NaasApiError) as exc_info:
            client.cancel_job("00000000-0000-0000-0000-000000000000")
        assert exc_info.value.status_code in {404, 403}


class TestSendCommand:
    """Test send_command against cisshgo (if available) or expect a connection error."""

    def test_send_command_and_poll(self, client: NaasClient) -> None:
        """Submit a job and poll until it finishes or fails.

        Without cisshgo running, the job will fail with a connection error —
        that's fine, we're testing the client round-trip, not the device.
        """
        job = client.send_command(
            host="cisshgo",
            platform="cisco_ios",
            port=10022,
            commands=["show version"],
        )
        assert job.job_id

        # Poll until terminal state
        result = job.poll()
        # Job may still be queued/started, keep polling
        import time

        deadline = time.time() + 30
        while time.time() < deadline:
            result = job.poll()
            if result.status in (JobStatus.FINISHED, JobStatus.FAILED):
                break
            time.sleep(1)

        assert result.status in (JobStatus.FINISHED, JobStatus.FAILED)


class TestAsyncClient:
    @pytest.mark.asyncio
    async def test_healthcheck(self, async_client: AsyncNaasClient) -> None:
        health = await async_client.healthcheck()
        assert health.status == "healthy"

    @pytest.mark.asyncio
    async def test_list_contexts(self, async_client: AsyncNaasClient) -> None:
        result = await async_client.list_contexts()
        assert len(result.contexts) >= 1
