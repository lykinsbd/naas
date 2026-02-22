"""Pytest configuration for integration tests."""

import subprocess
import time

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

    # Give services time to initialize
    print("⏳ Waiting for services to initialize...")
    time.sleep(15)

    # Check container status
    status = subprocess.run(
        ["docker", "compose", "-f", compose_file, "ps"],
        capture_output=True,
        text=True,
    )
    print(f"Container status:\n{status.stdout}")

    # Check API logs
    logs = subprocess.run(
        ["docker", "compose", "-f", compose_file, "logs", "api"],
        capture_output=True,
        text=True,
    )
    print(f"API logs:\n{logs.stdout[-500:]}")  # Last 500 chars

    yield

    # Cleanup
    print("\n🧹 Cleaning up Docker Compose stack...")
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "down", "-v"],
        check=False,
    )
