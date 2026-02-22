"""Pytest configuration for integration tests."""

import subprocess

import pytest


@pytest.fixture(scope="session", autouse=True)
def docker_compose():
    """Start Docker Compose stack for integration tests."""
    compose_file = "tests/integration/docker-compose.test.yml"

    # Start services
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d", "--build"],
        check=True,
        capture_output=True,
    )

    yield

    # Cleanup
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "down", "-v"],
        check=False,
        capture_output=True,
    )
