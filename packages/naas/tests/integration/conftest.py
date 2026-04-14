"""Pytest configuration for integration tests."""

import subprocess

import pytest


@pytest.fixture(scope="session", autouse=True)
def docker_compose():
    """Start Docker Compose stack for integration tests."""
    compose_file = "packages/naas/tests/integration/docker-compose.test.yml"

    print("\n🐳 Starting Docker Compose stack...")
    # Start services
    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d", "--build", "--wait"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Docker Compose stderr:\n{result.stderr}")
        print(f"Docker Compose stdout:\n{result.stdout}")
        raise RuntimeError(f"docker compose up failed (exit {result.returncode})")
    if result.stderr:
        print(f"Docker Compose output: {result.stderr}")

    # Wait for workers to register with Redis (python worker.py has startup delay)
    import time

    import requests

    for _ in range(30):
        try:
            r = requests.get("https://localhost:18443/healthcheck", verify=False, timeout=2)
            if r.status_code == 200:
                data = r.json()
                if data.get("components", {}).get("workers", {}).get("count", 0) > 0:
                    break
        except Exception:
            pass
        time.sleep(1)

    yield

    # Cleanup
    print("\n🧹 Cleaning up Docker Compose stack...")
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "down", "-v"],
        check=False,
    )
