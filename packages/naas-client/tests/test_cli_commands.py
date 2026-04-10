"""Tests for send-command and send-config CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from naas_client.cli import app
from naas_client.exceptions import NaasApiError, NaasJobError, NaasTimeoutError
from naas_client.models import JobResult

runner = CliRunner()

FINISHED_RESULT = JobResult.model_validate(
    {
        "job_id": "abc-123",
        "status": "finished",
        "results": {"show version": "Cisco IOS 15.1"},
    }
)

FAILED_RESULT = JobResult.model_validate(
    {
        "job_id": "abc-123",
        "status": "failed",
        "error": "Connection refused",
    }
)


def _mock_client(job_result: JobResult | None = None) -> MagicMock:
    mock = MagicMock()
    mock_job = MagicMock()
    mock_job.job_id = "abc-123"
    mock_job.wait.return_value = job_result or FINISHED_RESULT
    mock.send_command.return_value = mock_job
    mock.send_config.return_value = mock_job
    return mock


class TestSendCommand:
    @patch("naas_client.cli.NaasClient", autospec=True)
    def test_no_wait_json(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = _mock_client()
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "json",
                "send-command",
                "--host",
                "10.0.0.1",
                "show version",
            ],
        )
        assert result.exit_code == 0
        assert "abc-123" in result.output

    @patch("naas_client.cli.NaasClient", autospec=True)
    def test_wait_json(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = _mock_client()
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "json",
                "send-command",
                "--host",
                "10.0.0.1",
                "--wait",
                "show version",
            ],
        )
        assert result.exit_code == 0
        assert "finished" in result.output
        assert "Cisco IOS" in result.output

    @patch("naas_client.cli.NaasClient", autospec=True)
    def test_wait_human(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = _mock_client()
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "table",
                "send-command",
                "--host",
                "10.0.0.1",
                "--wait",
                "show version",
            ],
        )
        assert result.exit_code == 0
        assert "✓" in result.output

    @patch("naas_client.cli.NaasClient", autospec=True)
    def test_job_failed_exit_1(self, mock_cls: MagicMock) -> None:
        mock = _mock_client()
        mock.send_command.return_value.wait.side_effect = NaasJobError("abc-123", "Connection refused")
        mock_cls.return_value = mock
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "json",
                "send-command",
                "--host",
                "10.0.0.1",
                "--wait",
                "show version",
            ],
        )
        assert result.exit_code == 1

    @patch("naas_client.cli.NaasClient", autospec=True)
    def test_timeout_exit_4(self, mock_cls: MagicMock) -> None:
        mock = _mock_client()
        mock.send_command.return_value.wait.side_effect = NaasTimeoutError("timed out")
        mock_cls.return_value = mock
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "json",
                "send-command",
                "--host",
                "10.0.0.1",
                "--wait",
                "--timeout",
                "1",
                "show version",
            ],
        )
        assert result.exit_code == 4

    @patch("naas_client.cli.NaasClient", autospec=True)
    def test_api_error_exit_2(self, mock_cls: MagicMock) -> None:
        mock = _mock_client()
        mock.send_command.side_effect = NaasApiError(500, "ISE")
        mock_cls.return_value = mock
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "json",
                "send-command",
                "--host",
                "10.0.0.1",
                "show version",
            ],
        )
        assert result.exit_code == 2

    def test_missing_host(self) -> None:
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "send-command",
                "show version",
            ],
        )
        assert result.exit_code == 2
        assert "host" in result.output.lower()

    @patch("naas_client.cli.NaasClient", autospec=True)
    def test_expect_string(self, mock_cls: MagicMock) -> None:
        mock = _mock_client()
        mock_cls.return_value = mock
        runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "json",
                "send-command",
                "--host",
                "10.0.0.1",
                "--expect-string",
                "Router>",
                "show version",
            ],
        )
        call_kwargs = mock.send_command.call_args.kwargs
        assert call_kwargs["expect_string"] == "Router>"


class TestSendConfig:
    @patch("naas_client.cli.NaasClient", autospec=True)
    def test_no_wait(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = _mock_client()
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "json",
                "send-config",
                "--host",
                "10.0.0.1",
                "interface Gi0/1",
                "shutdown",
            ],
        )
        assert result.exit_code == 0
        assert "abc-123" in result.output

    @patch("naas_client.cli.NaasClient", autospec=True)
    def test_wait(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = _mock_client()
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "json",
                "send-config",
                "--host",
                "10.0.0.1",
                "--wait",
                "interface Gi0/1",
            ],
        )
        assert result.exit_code == 0
        assert "finished" in result.output

    @patch("naas_client.cli.NaasClient", autospec=True)
    def test_save_config_and_commit(self, mock_cls: MagicMock) -> None:
        mock = _mock_client()
        mock_cls.return_value = mock
        runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "json",
                "send-config",
                "--host",
                "10.0.0.1",
                "--save-config",
                "--commit",
                "set system hostname test",
            ],
        )
        call_kwargs = mock.send_config.call_args.kwargs
        assert call_kwargs["save_config"] is True
        assert call_kwargs["commit"] is True

    def test_missing_host(self) -> None:
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "send-config",
                "interface Gi0/1",
            ],
        )
        assert result.exit_code == 2
