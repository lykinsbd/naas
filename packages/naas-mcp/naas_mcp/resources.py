"""MCP resources for NAAS read-only data."""

import json

from fastmcp import Context
from naas_client import AsyncNaasClient

from naas_mcp.server import mcp


def _client(ctx: Context) -> AsyncNaasClient:
    return ctx.lifespan_context["client"]  # type: ignore[return-value]


@mcp.resource("naas://health", name="Health", description="NAAS API health status")
async def health(ctx: Context) -> str:
    """Current health status of the NAAS API."""
    result = await _client(ctx).healthcheck()
    return json.dumps(result.model_dump(mode="json"))


@mcp.resource("naas://contexts", name="Contexts", description="Available routing contexts")
async def contexts(ctx: Context) -> str:
    """List of active routing contexts configured in NAAS."""
    result = await _client(ctx).list_contexts()
    return json.dumps(result.model_dump(mode="json"))


@mcp.resource("naas://jobs/failed", name="Failed Jobs", description="Jobs in the failed registry")
async def failed_jobs(ctx: Context) -> str:
    """List of jobs that have failed and are in the dead letter registry."""
    result = await _client(ctx).failed_jobs()
    return json.dumps(result.model_dump(mode="json"))


@mcp.resource("naas://jobs", name="Jobs", description="Current job queue state")
async def jobs(ctx: Context) -> str:
    """Current jobs in the NAAS queue."""
    result = await _client(ctx).list_jobs()
    return json.dumps(result.model_dump(mode="json"))