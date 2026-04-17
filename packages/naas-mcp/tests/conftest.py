"""Shared fixtures for naas-mcp tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


def _make_test_server(mock_client: AsyncMock) -> FastMCP:
    """Build a FastMCP server with tools/resources wired to a mock client."""

    @asynccontextmanager
    async def test_lifespan(server: Any):
        yield {
            "client": mock_client,
            "job_poll_interval": 0.01,
            "job_timeout": 5,
        }

    server = FastMCP(name="naas-test", lifespan=test_lifespan)

    # Import tool/resource/prompt functions and register them on the test server
    from naas_mcp.prompts import config_push, show_commands, troubleshoot_device
    from naas_mcp.resources import contexts, failed_jobs, health, jobs
    from naas_mcp.tools import (
        cancel_job,
        create_api_key,
        get_job_result,
        list_jobs,
        revoke_api_key,
        send_command,
        send_command_structured,
        send_config,
    )

    for fn in (send_command, send_command_structured, send_config, get_job_result, cancel_job, list_jobs, create_api_key, revoke_api_key):
        server.add_tool(fn)

    server.resource("naas://health", name="Health")(health)
    server.resource("naas://contexts", name="Contexts")(contexts)
    server.resource("naas://jobs/failed", name="Failed Jobs")(failed_jobs)
    server.resource("naas://jobs", name="Jobs")(jobs)

    for fn in (show_commands, config_push, troubleshoot_device):
        server.add_prompt(fn)

    return server


@pytest.fixture
def mock_naas_client() -> AsyncMock:
    """A fully mocked AsyncNaasClient."""
    return AsyncMock()


@pytest.fixture
async def mcp_client(mock_naas_client: AsyncMock):
    """FastMCP Client wired to a test server with mocked NAAS client."""
    server = _make_test_server(mock_naas_client)
    async with Client(transport=server) as client:
        yield client
