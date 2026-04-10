"""CLI integration tests against a running NAAS docker-compose stack."""

from __future__ import annotations

from typer.testing import CliRunner

from naas_client.cli import app

runner = CliRunner()


class TestCliIntegration:
    """These tests require docker-compose to be running (conftest handles this)."""

    def test_healthcheck_json(self) -> None:
        result = runner.invoke(
            app,
            [
                "--url",
                "https://localhost:18443",
                "--username",
                "admin",
                "--password",
                "admin",
                "--no-verify",
                "--format",
                "json",
                "healthcheck",
            ],
        )
        assert result.exit_code == 0
        assert '"healthy"' in result.output

    def test_healthcheck_table(self) -> None:
        result = runner.invoke(
            app,
            [
                "--url",
                "https://localhost:18443",
                "--username",
                "admin",
                "--password",
                "admin",
                "--no-verify",
                "--format",
                "table",
                "healthcheck",
            ],
        )
        assert result.exit_code == 0
        assert "healthy" in result.output

    def test_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "naas-client" in result.output

    def test_contexts_list(self) -> None:
        result = runner.invoke(
            app,
            [
                "--url",
                "https://localhost:18443",
                "--username",
                "admin",
                "--password",
                "admin",
                "--no-verify",
                "--format",
                "json",
                "contexts",
                "list",
            ],
        )
        assert result.exit_code == 0
        assert "default" in result.output

    def test_jobs_list(self) -> None:
        result = runner.invoke(
            app,
            [
                "--url",
                "https://localhost:18443",
                "--username",
                "admin",
                "--password",
                "admin",
                "--no-verify",
                "--format",
                "json",
                "jobs",
                "list",
            ],
        )
        assert result.exit_code == 0
        assert "pagination" in result.output
