"""Tests for CLI app and healthcheck command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from naas_client.cli import app
from naas_client.exceptions import NaasApiError, NaasAuthError
from naas_client.models import HealthCheckResponse

runner = CliRunner()

HEALTH_DATA = HealthCheckResponse.model_validate(
    {
        "status": "healthy",
        "version": "2.0.0",
        "uptime_seconds": 100,
        "components": {
            "redis": {"status": "healthy"},
            "queue": {"status": "healthy", "depth": 0},
            "workers": {"status": "healthy", "count": 4, "active_jobs": 0},
            "failed_jobs": 0,
        },
    }
)


class TestVersion:
    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "naas-client" in result.output


class TestHealthcheck:
    @patch("naas_client.cli.NaasClient")
    def test_healthcheck_json(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.healthcheck.return_value = HEALTH_DATA
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "healthcheck"])
        assert result.exit_code == 0
        assert '"healthy"' in result.output
        assert '"version"' in result.output
        mock_client.close.assert_called_once()

    @patch("naas_client.cli.NaasClient")
    def test_healthcheck_table(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.healthcheck.return_value = HEALTH_DATA
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["--url", "https://test", "--format", "table", "healthcheck"])
        assert result.exit_code == 0
        assert "healthy" in result.output
        mock_client.close.assert_called_once()

    def test_healthcheck_no_url(self) -> None:
        result = runner.invoke(app, ["healthcheck"], env={"NAAS_CONFIG": "/nonexistent"})
        assert result.exit_code == 2
        assert "URL required" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_healthcheck_api_error(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.healthcheck.side_effect = NaasApiError(500, "Internal Server Error")
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "healthcheck"])
        assert result.exit_code == 2

    @patch("naas_client.cli.NaasClient")
    def test_healthcheck_auth_error(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.healthcheck.side_effect = NaasAuthError(401, "Unauthorized")
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "healthcheck"])
        assert result.exit_code == 3


class TestGlobalOptions:
    @patch("naas_client.cli.NaasClient")
    def test_all_options_passed(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.healthcheck.return_value = HEALTH_DATA
        mock_cls.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--username",
                "admin",
                "--password",
                "secret",
                "--no-verify",
                "--format",
                "json",
                "healthcheck",
            ],
        )
        assert result.exit_code == 0
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs["username"] == "admin"
        assert call_kwargs.kwargs["verify"] is False

    @patch("naas_client.cli.NaasClient")
    def test_api_key_option(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.healthcheck.return_value = HEALTH_DATA
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["--url", "https://test", "--api-key", "jwt", "--format", "json", "healthcheck"])
        assert result.exit_code == 0
        assert mock_cls.call_args.kwargs["api_key"] == "jwt"
