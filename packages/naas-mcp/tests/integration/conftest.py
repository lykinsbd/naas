"""Integration test fixtures — spins up NAAS docker-compose stack.

Reuses the same docker-compose.test.yml as the server/client integration tests.
"""

from __future__ import annotations

import subprocess
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from naas_client import AsyncNaasClient

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
def docker_compose():  # type: ignore[misc]
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
async def integration_mcp_client():
    """FastMCP Client wired to a real NAAS API via AsyncNaasClient."""

    @asynccontextmanager
    async def real_lifespan(server: Any):
        client = AsyncNaasClient(base_url=BASE_URL, username=USERNAME, password=PASSWORD, verify=False)
        try:
            yield {"client": client, "job_poll_interval": 1.0, "job_timeout": 30.0}
        finally:
            await client.close()

    server = FastMCP(name="naas-integration", lifespan=real_lifespan)

    from naas_mcp.resources import contexts, failed_jobs, health
    from naas_mcp.tools import cancel_job, get_job_result, list_jobs, send_command, send_config

    for fn in (send_command, send_config, get_job_result, cancel_job, list_jobs):
        server.add_tool(fn)
    server.resource("naas://health", name="Health")(health)
    server.resource("naas://contexts", name="Contexts")(contexts)
    server.resource("naas://jobs/failed", name="Failed Jobs")(failed_jobs)

    async with Client(transport=server) as client:
        yield client
