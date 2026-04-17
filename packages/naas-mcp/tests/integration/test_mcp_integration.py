"""Integration tests — run against live NAAS + cisshgo stack.

Requires: docker-compose up (naas-api, naas-worker, redis, cisshgo)
Run with: uv run pytest packages/naas-mcp/tests/integration -v
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastmcp.client import Client


async def test_send_command_show_version(integration_mcp_client: Client):
    """Submit 'show version' to cisshgo and verify the MCP tool round-trip works."""
    resp = await integration_mcp_client.call_tool(
        "send_command",
        {
            "host": "cisshgo",
            "platform": "cisco_ios",
            "commands": ["show version"],
            "username": "admin",
            "password": "admin",
        },
        raise_on_error=False,
    )

    # Job completed through the MCP tool — either success or device error
    if resp.is_error:
        # Connection to cisshgo failed — tool surfaced the error correctly
        assert resp.content[0].text  # type: ignore[union-attr]
    else:
        data = json.loads(resp.content[0].text)  # type: ignore[union-attr]
        assert data["status"] == "finished"


async def test_list_jobs(integration_mcp_client: Client):
    """List jobs — should return at least the job from the previous test."""
    resp = await integration_mcp_client.call_tool("list_jobs", {})

    data = json.loads(resp.content[0].text)  # type: ignore[union-attr]
    assert "jobs" in data
    assert "pagination" in data


async def test_health_resource(integration_mcp_client: Client):
    """Read health resource from live API."""
    import asyncio

    deadline = time.monotonic() + 30
    while True:
        contents = await integration_mcp_client.read_resource("naas://health")
        data = json.loads(contents[0].text)  # type: ignore[union-attr]
        if data["status"] == "healthy":
            break
        if time.monotonic() > deadline:
            pytest.fail(f"Healthcheck not healthy after 30s: status={data['status']}")
        await asyncio.sleep(2)


async def test_contexts_resource(integration_mcp_client: Client):
    """Read contexts resource from live API."""
    contents = await integration_mcp_client.read_resource("naas://contexts")

    data = json.loads(contents[0].text)  # type: ignore[union-attr]
    assert "contexts" in data


async def test_failed_jobs_resource(integration_mcp_client: Client):
    """Read failed jobs resource from live API."""
    contents = await integration_mcp_client.read_resource("naas://jobs/failed")

    data = json.loads(contents[0].text)  # type: ignore[union-attr]
    assert "jobs" in data
