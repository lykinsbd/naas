"""Tests for jobs CLI subcommand group."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from naas_client.cli import app
from naas_client.exceptions import NaasApiError
from naas_client.models import (
    FailedJobsResponse,
    JobResult,
    JobSubmission,
    ListJobsResponse,
)

runner = CliRunner()

JOBS_LIST = ListJobsResponse.model_validate(
    {
        "jobs": [{"job_id": "abc-123", "status": "finished", "created_at": "2026-04-10T00:00:00Z", "tags": None}],
        "pagination": {"page": 1, "per_page": 20, "total": 1, "pages": 1},
    }
)

FAILED_LIST = FailedJobsResponse.model_validate(
    {
        "jobs": [
            {
                "job_id": "def-456",
                "host": "10.0.0.1",
                "platform": "cisco_ios",
                "failed_at": "2026-04-10T00:00:00Z",
                "error": "timeout",
            }
        ],
        "total": 1,
    }
)

JOB_FINISHED = JobResult.model_validate(
    {"job_id": "abc-123", "status": "finished", "results": {"show version": "Cisco"}}
)
JOB_FAILED = JobResult.model_validate({"job_id": "abc-123", "status": "failed", "error": "Connection refused"})
JOB_SUBMISSION = JobSubmission.model_validate(
    {
        "job_id": "new-789",
        "message": "Replayed",
        "queue_position": 0,
        "enqueued_at": "2026-04-10T00:00:00Z",
        "timeout": 300,
    }
)


class TestJobsList:
    @patch("naas_client.cli.NaasClient")
    def test_list_json(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(list_jobs=MagicMock(return_value=JOBS_LIST))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "jobs", "list"])
        assert result.exit_code == 0
        assert "abc-123" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_list_table(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(list_jobs=MagicMock(return_value=JOBS_LIST))
        result = runner.invoke(app, ["--url", "https://test", "--format", "table", "jobs", "list"])
        assert result.exit_code == 0
        assert "abc-123" in result.output
        assert "Page 1/1" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_list_with_filters(self, mock_cls: MagicMock) -> None:
        mock = MagicMock(list_jobs=MagicMock(return_value=JOBS_LIST))
        mock_cls.return_value = mock
        runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "json",
                "jobs",
                "list",
                "--status",
                "failed",
                "--tag",
                "env:prod",
                "--page",
                "2",
            ],
        )
        mock.list_jobs.assert_called_once_with(page=2, per_page=20, status="failed", tag="env:prod")

    @patch("naas_client.cli.NaasClient")
    def test_list_api_error(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(list_jobs=MagicMock(side_effect=NaasApiError(500, "ISE")))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "jobs", "list"])
        assert result.exit_code == 2


class TestJobsGet:
    @patch("naas_client.cli.NaasClient")
    def test_get_finished(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(get_command_result=MagicMock(return_value=JOB_FINISHED))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "jobs", "get", "abc-123"])
        assert result.exit_code == 0
        assert "finished" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_get_failed_exit_1(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(get_command_result=MagicMock(return_value=JOB_FAILED))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "jobs", "get", "abc-123"])
        assert result.exit_code == 1

    @patch("naas_client.cli.NaasClient")
    def test_get_api_error(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(get_command_result=MagicMock(side_effect=NaasApiError(404, "Not found")))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "jobs", "get", "abc-123"])
        assert result.exit_code == 2


class TestJobsCancel:
    @patch("naas_client.cli.NaasClient")
    def test_cancel(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(cancel_job=MagicMock())
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "jobs", "cancel", "abc-123"])
        assert result.exit_code == 0
        assert "cancelled" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_cancel_api_error(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(cancel_job=MagicMock(side_effect=NaasApiError(404, "Not found")))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "jobs", "cancel", "abc-123"])
        assert result.exit_code == 2


class TestJobsReplay:
    @patch("naas_client.cli.NaasClient")
    def test_replay(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(replay_job=MagicMock(return_value=JOB_SUBMISSION))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "jobs", "replay", "abc-123"])
        assert result.exit_code == 0
        assert "new-789" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_replay_api_error(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(replay_job=MagicMock(side_effect=NaasApiError(404, "Not found")))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "jobs", "replay", "abc-123"])
        assert result.exit_code == 2


class TestJobsFailed:
    @patch("naas_client.cli.NaasClient")
    def test_failed_json(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(failed_jobs=MagicMock(return_value=FAILED_LIST))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "jobs", "failed"])
        assert result.exit_code == 0
        assert "def-456" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_failed_table(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(failed_jobs=MagicMock(return_value=FAILED_LIST))
        result = runner.invoke(app, ["--url", "https://test", "--format", "table", "jobs", "failed"])
        assert result.exit_code == 0
        assert "timeout" in result.output
        assert "1 failed" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_failed_api_error(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(failed_jobs=MagicMock(side_effect=NaasApiError(500, "ISE")))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "jobs", "failed"])
        assert result.exit_code == 2
