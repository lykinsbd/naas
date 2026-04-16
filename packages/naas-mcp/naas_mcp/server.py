"""FastMCP server definition and configuration."""

from __future__ import annotations

import os

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from naas_client import AsyncNaasClient


def _get_config() -> dict[str, str | int | float]:
    """Read configuration from environment variables."""
    return {
        "api_url": os.environ.get("NAAS_MCP_API_URL", "http://localhost:8080"),
        "api_key": os.environ.get("NAAS_MCP_API_KEY", ""),
        "timeout": float(os.environ.get("NAAS_MCP_TIMEOUT", "30")),
        "job_poll_interval": float(os.environ.get("NAAS_MCP_JOB_POLL_INTERVAL", "2")),
        "job_timeout": float(os.environ.get("NAAS_MCP_JOB_TIMEOUT", "300")),
    }


@lifespan
async def app_lifespan(server: FastMCP):  # type: ignore[type-arg]
    """Initialize AsyncNaasClient for the server lifetime."""
    cfg = _get_config()
    client = AsyncNaasClient(
        base_url=str(cfg["api_url"]),
        api_key=str(cfg["api_key"]) or None,
        timeout=float(cfg["timeout"]),
    )
    try:
        yield {
            "client": client,
            "job_poll_interval": float(cfg["job_poll_interval"]),
            "job_timeout": float(cfg["job_timeout"]),
        }
    finally:
        await client.close()


mcp = FastMCP(
    name="naas",
    instructions=(
        "NAAS MCP server for AI-assisted network operations. "
        "Use tools to send commands/configs to network devices and manage jobs. "
        "Use resources to read health status, available contexts, and failed jobs."
    ),
    lifespan=app_lifespan,
)

# Register tools and resources via imports (side effects)
import naas_mcp.resources  # noqa: E402, F401
import naas_mcp.tools  # noqa: E402, F401
