"""Integration tests — run against live NAAS + cisshgo stack.

Requires: docker-compose up (naas-api, naas-worker, redis, cisshgo)
Run with: uv run pytest packages/naas-mcp/tests/integration -v
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp.client import Client


async def test_send_command_show_version(integration_mcp_client: Client):
    """Submit 'show version' to cisshgo and verify result."""
    resp = await integration_mcp_client.call_tool(
        "send_command",
        {
            "host": "cisshgo",
            "platform": "cisco_ios",
            "commands": ["show version"],
            "username": "admin",
            "password": "admin",
        },
    )

    data = json.loads(resp.content[0].text)  # type: ignore[union-attr]
    assert data["status"] == "finished"
    assert data["results"] is not None


async def test_list_jobs(integration_mcp_client: Client):
    """List jobs — should return at least the job from the previous test."""
    resp = await integration_mcp_client.call_tool("list_jobs", {})

    data = json.loads(resp.content[0].text)  # type: ignore[union-attr]
    assert "jobs" in data
    assert "pagination" in data


async def test_health_resource(integration_mcp_client: Client):
    """Read health resource from live API."""
    contents = await integration_mcp_client.read_resource("naas://health")

    data = json.loads(contents[0].text)  # type: ignore[union-attr]
    assert data["status"] == "healthy"


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
