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
        "transport": os.environ.get("NAAS_MCP_TRANSPORT", "stdio"),
        "jwt_secret": os.environ.get("NAAS_JWT_SECRET", ""),
        "redis_url": os.environ.get("NAAS_MCP_REDIS_URL", ""),
    }


def _get_auth_provider():
    """Create auth provider for HTTP transport, None for stdio."""
    cfg = _get_config()
    if cfg["transport"] == "stdio":
        return None

    jwt_secret = str(cfg["jwt_secret"])
    if not jwt_secret:
        raise RuntimeError(
            "NAAS_JWT_SECRET is required when running with HTTP transport. "
            "Set it to the same value used by the NAAS API server."
        )

    from naas_mcp.auth import NaasAuthProvider

    redis_url = str(cfg["redis_url"]) or None
    return NaasAuthProvider(jwt_secret=jwt_secret, redis_url=redis_url)


def _get_middleware():
    """Create authorization middleware for HTTP transport."""
    cfg = _get_config()
    if cfg["transport"] == "stdio":
        return None

    from fastmcp.server.middleware.authorization import AuthMiddleware

    from naas_mcp.rbac import require_naas_role

    return AuthMiddleware(auth=require_naas_role)


@lifespan
async def app_lifespan(server: FastMCP):  # type: ignore[type-arg]
    """Initialize AsyncNaasClient for the server lifetime.

    In stdio mode: creates a single client with the configured API key.
    In HTTP mode: creates a base client (tools override auth per-request).
    """
    cfg = _get_config()
    api_key = str(cfg["api_key"]) or None

    client = AsyncNaasClient(
        base_url=str(cfg["api_url"]),
        api_key=api_key,
        timeout=float(cfg["timeout"]),
    )
    try:
        yield {
            "client": client,
            "job_poll_interval": float(cfg["job_poll_interval"]),
            "job_timeout": float(cfg["job_timeout"]),
            "transport": str(cfg["transport"]),
            "api_url": str(cfg["api_url"]),
            "timeout": float(cfg["timeout"]),
        }
    finally:
        await client.close()


# Build middleware list (only include auth middleware for HTTP)
_middleware = _get_middleware()
_middleware_list = [_middleware] if _middleware is not None else None

mcp = FastMCP(
    name="naas",
    instructions=(
        "NAAS MCP server for AI-assisted network operations. "
        "Use tools to send commands/configs to network devices and manage jobs. "
        "Use resources to read health status, available contexts, and failed jobs."
    ),
    lifespan=app_lifespan,
    auth=_get_auth_provider(),
    middleware=_middleware_list,
)

# Register tools, resources, and prompts via imports (side effects)
import naas_mcp.prompts  # noqa: E402, F401
import naas_mcp.resources  # noqa: E402, F401
import naas_mcp.tools  # noqa: E402, F401
