"""End-to-end CLI integration tests against a running NAAS + cisshgo stack."""

from __future__ import annotations

import json
import socket
import time

import pytest
from typer.testing import CliRunner

from naas_client.cli import app

runner = CliRunner()

CISSHGO_HOST = "240.11.2.100"
CISSHGO_PORT = 10022

BASE_OPTS = [
    "--url",
    "https://localhost:18443",
    "--username",
    "admin",
    "--password",
    "admin",
    "--no-verify",
    "--format",
    "json",
]


@pytest.fixture(scope="session")
def wait_for_cisshgo() -> None:
    """Wait for cisshgo SSH port to be ready."""
    for _ in range(30):
        try:
            with socket.create_connection(("localhost", CISSHGO_PORT), timeout=2):
                return
        except OSError:
            pass
        time.sleep(1)
    pytest.fail("cisshgo did not become ready in 30s")


class TestCliEndToEnd:
    def test_send_command_wait(self, docker_compose: None, wait_for_cisshgo: None) -> None:
        """Submit a command via CLI, wait for result, verify output."""
        result = runner.invoke(
            app,
            [
                *BASE_OPTS,
                "send-command",
                "--host",
                CISSHGO_HOST,
                "--platform",
                "cisco_ios",
                "--port",
                str(CISSHGO_PORT),
                "--wait",
                "--timeout",
                "30",
                "show version",
            ],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        data = json.loads(result.output)
        assert data["status"] == "finished"
        assert "Cisco IOS" in data["results"]["show version"]

    def test_jobs_list_shows_job(self, docker_compose: None, wait_for_cisshgo: None) -> None:
        """After submitting a job, jobs list should return results."""
        result = runner.invoke(app, [*BASE_OPTS, "jobs", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["pagination"]["total"] >= 1

    def test_jobs_get(self, docker_compose: None, wait_for_cisshgo: None) -> None:
        """Submit a job, then get it by ID."""
        # Submit
        submit = runner.invoke(
            app,
            [
                *BASE_OPTS,
                "send-command",
                "--host",
                CISSHGO_HOST,
                "--platform",
                "cisco_ios",
                "--port",
                str(CISSHGO_PORT),
                "show version",
            ],
        )
        assert submit.exit_code == 0
        job_id = json.loads(submit.output)["job_id"]

        # Wait for completion
        import time as _time

        deadline = _time.time() + 30
        while _time.time() < deadline:
            get_result = runner.invoke(app, [*BASE_OPTS, "jobs", "get", job_id])
            assert get_result.exit_code in (0, 1)
            data = json.loads(get_result.output)
            if data["status"] in ("finished", "failed"):
                break
            _time.sleep(1)

        assert data["status"] == "finished"

    def test_send_config_wait(self, docker_compose: None, wait_for_cisshgo: None) -> None:
        """Submit a config via CLI, wait for result."""
        result = runner.invoke(
            app,
            [
                *BASE_OPTS,
                "send-config",
                "--host",
                CISSHGO_HOST,
                "--platform",
                "cisco_ios",
                "--port",
                str(CISSHGO_PORT),
                "--wait",
                "--timeout",
                "30",
                "interface Loopback0",
                "description cli-test",
            ],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        data = json.loads(result.output)
        assert data["status"] == "finished"

    def test_contexts_list(self, docker_compose: None) -> None:
        """Contexts list returns at least default."""
        result = runner.invoke(app, [*BASE_OPTS, "contexts", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        names = [c["name"] for c in data["contexts"]]
        assert "default" in names
