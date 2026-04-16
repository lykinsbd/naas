"""Integration test fixtures — requires running NAAS stack (docker-compose)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client

from naas_client import AsyncNaasClient

NAAS_URL = os.environ.get("NAAS_INTEGRATION_URL", "http://localhost:8080")
NAAS_USER = os.environ.get("NAAS_INTEGRATION_USER", "admin")
NAAS_PASS = os.environ.get("NAAS_INTEGRATION_PASS", "admin")


@pytest.fixture
async def integration_mcp_client():
    """FastMCP Client wired to a real NAAS API via AsyncNaasClient."""

    @asynccontextmanager
    async def real_lifespan(server: Any):
        client = AsyncNaasClient(base_url=NAAS_URL, username=NAAS_USER, password=NAAS_PASS)
        try:
            yield {"client": client, "job_poll_interval": 1.0, "job_timeout": 30.0}
        finally:
            await client.close()

    server = FastMCP(name="naas-integration", lifespan=real_lifespan)

    from naas_mcp.tools import cancel_job, get_job_result, list_jobs, send_command, send_config
    from naas_mcp.resources import contexts, failed_jobs, health

    for fn in (send_command, send_config, get_job_result, cancel_job, list_jobs):
        server.add_tool(fn)
    server.resource("naas://health", name="Health")(health)
    server.resource("naas://contexts", name="Contexts")(contexts)
    server.resource("naas://jobs/failed", name="Failed Jobs")(failed_jobs)

    async with Client(transport=server) as client:
        yield client
