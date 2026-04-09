"""Pytest configuration for naas-client integration tests.

Reuses the NAAS docker-compose stack. Start it before running:
    docker compose -f packages/naas/tests/integration/docker-compose.test.yml up -d --build --wait
"""

from __future__ import annotations

import subprocess
import time

import httpx
import pytest
import pytest_asyncio

from naas_client.async_client import AsyncNaasClient
from naas_client.client import NaasClient

COMPOSE_FILE = "packages/naas/tests/integration/docker-compose.test.yml"
BASE_URL = "https://localhost:18443"
USERNAME = "admin"
PASSWORD = "admin"


def _wait_for_api(url: str, timeout: int = 60) -> None:
    """Poll healthcheck until the API is ready with workers."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{url}/healthcheck", verify=False, timeout=2)
            if r.status_code == 200:
                data = r.json()
                workers = data.get("components", {}).get("workers", {}).get("count", 0)
                if workers > 0:
                    return
        except httpx.TransportError:
            pass
        time.sleep(2)
    raise RuntimeError(f"API at {url} did not become ready in {timeout}s")


@pytest.fixture(scope="session", autouse=True)
def docker_compose() -> None:  # type: ignore[misc]
    """Start Docker Compose stack for integration tests."""
    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "--build", "--wait"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker compose up failed (exit {result.returncode})\n{result.stderr}")

    _wait_for_api(BASE_URL)
    yield
    subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "down", "-v"], check=False)


@pytest.fixture
def client() -> NaasClient:  # type: ignore[misc]
    """Sync client for integration tests."""
    c = NaasClient(BASE_URL, username=USERNAME, password=PASSWORD, verify=False)
    yield c  # type: ignore[misc]
    c.close()


@pytest_asyncio.fixture
async def async_client() -> AsyncNaasClient:  # type: ignore[misc]
    """Async client for integration tests."""
    c = AsyncNaasClient(BASE_URL, username=USERNAME, password=PASSWORD, verify=False)
    yield c  # type: ignore[misc]
    await c.close()
