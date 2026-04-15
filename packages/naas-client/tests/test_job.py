"""Tests for naas_client.job.Job."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from naas_client.exceptions import NaasConnectionError, NaasDeviceAuthError, NaasJobError, NaasTimeoutError
from naas_client.job import Job
from naas_client.models import JobResult, JobSubmission


def _mock_client() -> MagicMock:
    return MagicMock(spec_set=["get_command_result", "get_config_result", "cancel_job", "replay_job"])


def _job_result(status: str = "finished", **kwargs: object) -> JobResult:
    return JobResult.model_validate({"job_id": "abc-123", "status": status, **kwargs})


class TestPoll:
    def test_poll_command(self) -> None:
        client = _mock_client()
        client.get_command_result.return_value = _job_result()
        job = Job(client, "abc-123", "command")
        result = job.poll()
        assert result.status == "finished"
        client.get_command_result.assert_called_once_with("abc-123")

    def test_poll_config(self) -> None:
        client = _mock_client()
        client.get_config_result.return_value = _job_result()
        job = Job(client, "abc-123", "config")
        job.poll()
        client.get_config_result.assert_called_once_with("abc-123")


class TestWait:
    @patch("naas_client.job.time.sleep")
    @patch("naas_client.job.time.monotonic")
    def test_wait_returns_on_finished(self, mock_mono: MagicMock, mock_sleep: MagicMock) -> None:
        mock_mono.side_effect = [0.0, 0.5]  # start, first poll
        client = _mock_client()
        client.get_command_result.return_value = _job_result("finished")
        job = Job(client, "abc-123", "command")
        result = job.wait(timeout=10)
        assert result.status == "finished"
        mock_sleep.assert_not_called()

    @patch("naas_client.job.time.sleep")
    @patch("naas_client.job.time.monotonic")
    def test_wait_polls_until_done(self, mock_mono: MagicMock, mock_sleep: MagicMock) -> None:
        mock_mono.side_effect = [0.0, 1.0, 2.0, 3.0]
        client = _mock_client()
        client.get_command_result.side_effect = [
            _job_result("queued"),
            _job_result("started"),
            _job_result("finished", results={"show version": "Cisco"}),
        ]
        job = Job(client, "abc-123", "command")
        result = job.wait(timeout=10)
        assert result.status == "finished"
        assert mock_sleep.call_count == 2

    @patch("naas_client.job.time.sleep")
    @patch("naas_client.job.time.monotonic")
    def test_wait_raises_on_failure(self, mock_mono: MagicMock, mock_sleep: MagicMock) -> None:
        mock_mono.side_effect = [0.0, 0.5]
        client = _mock_client()
        client.get_command_result.return_value = _job_result(
            "failed", error="Connection refused", error_code="CONNECTION_TIMEOUT", error_retryable=True
        )
        job = Job(client, "abc-123", "command")
        with pytest.raises(NaasConnectionError) as exc_info:
            job.wait(timeout=10)
        assert exc_info.value.error == "Connection refused"
        assert exc_info.value.error_code == "CONNECTION_TIMEOUT"
        assert exc_info.value.error_retryable is True

    @patch("naas_client.job.time.sleep")
    @patch("naas_client.job.time.monotonic")
    def test_wait_raises_on_failure_no_error_msg(self, mock_mono: MagicMock, mock_sleep: MagicMock) -> None:
        mock_mono.side_effect = [0.0, 0.5]
        client = _mock_client()
        client.get_command_result.return_value = _job_result("failed")
        job = Job(client, "abc-123", "command")
        with pytest.raises(NaasJobError) as exc_info:
            job.wait(timeout=10)
        assert exc_info.value.error == "Unknown error"

    @patch("naas_client.job.time.sleep")
    @patch("naas_client.job.time.monotonic")
    def test_wait_raises_subclass_for_auth_failure(self, mock_mono: MagicMock, mock_sleep: MagicMock) -> None:
        mock_mono.side_effect = [0.0, 0.5]
        client = _mock_client()
        client.get_command_result.return_value = _job_result(
            "failed", error="Auth failed", error_code="AUTH_FAILURE", error_retryable=False
        )
        job = Job(client, "abc-123", "command")
        with pytest.raises(NaasDeviceAuthError):
            job.wait(timeout=10)

    @patch("naas_client.job.time.sleep")
    @patch("naas_client.job.time.monotonic")
    def test_wait_timeout(self, mock_mono: MagicMock, mock_sleep: MagicMock) -> None:
        mock_mono.side_effect = [0.0, 5.0, 11.0]
        client = _mock_client()
        client.get_command_result.return_value = _job_result("queued")
        job = Job(client, "abc-123", "command")
        with pytest.raises(NaasTimeoutError, match="did not complete"):
            job.wait(timeout=10)


class TestProperties:
    def test_is_complete_before_poll(self) -> None:
        job = Job(_mock_client(), "abc-123", "command")
        assert job.is_complete is False
        assert job.is_failed is False
        assert job.result is None

    def test_is_complete_after_finished(self) -> None:
        client = _mock_client()
        client.get_command_result.return_value = _job_result("finished")
        job = Job(client, "abc-123", "command")
        job.poll()
        assert job.is_complete is True
        assert job.is_failed is False

    def test_is_failed(self) -> None:
        client = _mock_client()
        client.get_command_result.return_value = _job_result("failed")
        job = Job(client, "abc-123", "command")
        job.poll()
        assert job.is_complete is True
        assert job.is_failed is True

    def test_not_complete_while_running(self) -> None:
        client = _mock_client()
        client.get_command_result.return_value = _job_result("started")
        job = Job(client, "abc-123", "command")
        job.poll()
        assert job.is_complete is False


class TestActions:
    def test_cancel(self) -> None:
        client = _mock_client()
        job = Job(client, "abc-123", "command")
        job.cancel()
        client.cancel_job.assert_called_once_with("abc-123")

    def test_replay(self) -> None:
        client = _mock_client()
        client.replay_job.return_value = JobSubmission.model_validate(
            {
                "job_id": "new-456",
                "message": "Replayed",
                "queue_position": 0,
                "enqueued_at": "2026-01-01T00:00:00Z",
                "timeout": 300,
            }
        )
        job = Job(client, "abc-123", "command")
        new_job = job.replay()
        assert new_job.job_id == "new-456"
        assert isinstance(new_job, Job)
