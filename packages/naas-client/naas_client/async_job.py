"""Async Job object with polling and wait support."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from naas_client.exceptions import NaasJobError, NaasTimeoutError
from naas_client.models import JobResult, JobStatus

if TYPE_CHECKING:
    from naas_client.async_client import AsyncNaasClient


class AsyncJob:
    """An async submitted NAAS job with polling and wait capabilities."""

    def __init__(self, client: AsyncNaasClient, job_id: str, job_type: str) -> None:
        self._client = client
        self.job_id = job_id
        self._job_type = job_type
        self._result: JobResult | None = None

    async def poll(self) -> JobResult:
        """Fetch current job status (single request)."""
        if self._job_type == "config":
            self._result = await self._client.get_config_result(self.job_id)
        else:
            self._result = await self._client.get_command_result(self.job_id)
        return self._result

    async def wait(self, *, timeout: float = 60, interval: float = 1.0) -> JobResult:
        """Await until job completes or timeout.

        Raises:
            NaasTimeoutError: If timeout exceeded.
            NaasJobError: If job failed.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            result = await self.poll()
            if result.status in (JobStatus.FINISHED, JobStatus.FAILED):
                if result.status == JobStatus.FAILED:
                    raise NaasJobError(self.job_id, result.error or "Unknown error")
                return result
            await asyncio.sleep(interval)
        raise NaasTimeoutError(f"Job {self.job_id} did not complete within {timeout}s")

    @property
    def is_complete(self) -> bool:
        return self._result is not None and self._result.status in (JobStatus.FINISHED, JobStatus.FAILED)

    @property
    def is_failed(self) -> bool:
        return self._result is not None and self._result.status == JobStatus.FAILED

    @property
    def result(self) -> JobResult | None:
        return self._result

    async def cancel(self) -> None:
        await self._client.cancel_job(self.job_id)

    async def replay(self) -> AsyncJob:
        submission = await self._client.replay_job(self.job_id)
        return AsyncJob(self._client, submission.job_id, self._job_type)
