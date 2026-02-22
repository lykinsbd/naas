"""Pytest configuration for integration tests."""

import subprocess

import pytest


@pytest.fixture(scope="session", autouse=True)
def docker_compose():
    """Start Docker Compose stack for integration tests."""
    compose_file = "tests/integration/docker-compose.test.yml"

    print("\n🐳 Starting Docker Compose stack...")
    # Start services
    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d", "--build"],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stderr:
        print(f"Docker Compose output: {result.stderr}")

    yield

    # Cleanup
    print("\n🧹 Cleaning up Docker Compose stack...")
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "down", "-v"],
        check=False,
    )
