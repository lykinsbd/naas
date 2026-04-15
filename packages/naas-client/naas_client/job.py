"""Job object with polling and wait support."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from naas_client.exceptions import NaasTimeoutError, _job_error_from_result
from naas_client.models import JobResult, JobStatus

if TYPE_CHECKING:
    from naas_client.client import NaasClient


class Job:
    """A submitted NAAS job with polling and wait capabilities.

    Args:
        client: NaasClient instance for polling.
        job_id: Job identifier.
        job_type: "command" or "config" (determines polling endpoint).
    """

    def __init__(self, client: NaasClient, job_id: str, job_type: str) -> None:
        self._client = client
        self.job_id = job_id
        self._job_type = job_type
        self._result: JobResult | None = None

    def poll(self) -> JobResult:
        """Fetch current job status (single request)."""
        if self._job_type == "config":
            self._result = self._client.get_config_result(self.job_id)
        else:
            self._result = self._client.get_command_result(self.job_id)
        return self._result

    def wait(self, *, timeout: float = 60, interval: float = 1.0) -> JobResult:
        """Block until job completes or timeout.

        Args:
            timeout: Maximum seconds to wait.
            interval: Seconds between polls.

        Returns:
            JobResult with final status.

        Raises:
            NaasTimeoutError: If timeout exceeded.
            NaasJobError: If job failed.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.poll()
            if result.status in (JobStatus.FINISHED, JobStatus.FAILED):
                if result.status == JobStatus.FAILED:
                    raise _job_error_from_result(self.job_id, result.error, result.error_code, result.error_retryable)
                return result
            time.sleep(interval)
        raise NaasTimeoutError(f"Job {self.job_id} did not complete within {timeout}s")

    @property
    def is_complete(self) -> bool:
        """True if last poll showed finished or failed."""
        return self._result is not None and self._result.status in (JobStatus.FINISHED, JobStatus.FAILED)

    @property
    def is_failed(self) -> bool:
        """True if last poll showed failed."""
        return self._result is not None and self._result.status == JobStatus.FAILED

    @property
    def result(self) -> JobResult | None:
        """Last polled result, or None if never polled."""
        return self._result

    def cancel(self) -> None:
        """Cancel this job."""
        self._client.cancel_job(self.job_id)

    def replay(self) -> Job:
        """Re-enqueue this job. Returns a new Job."""
        submission = self._client.replay_job(self.job_id)
        return Job(self._client, submission.job_id, self._job_type)
