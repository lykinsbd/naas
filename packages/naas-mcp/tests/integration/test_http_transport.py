"""Integration tests for MCP server running in streamable-http mode with Bearer token auth.

Tests the HTTP transport layer with JWT authentication:
- Valid Bearer tokens are accepted and allow MCP protocol interaction
- Invalid/missing tokens are rejected with appropriate HTTP status codes

Uses FastMCP's http_app() + httpx ASGITransport with manual lifespan management
instead of Docker.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import httpx
import jwt
import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.auth.bearer import BearerAuth
from fastmcp.client.transports.http import StreamableHttpTransport

from naas_mcp.auth import NaasAuthProvider
from naas_mcp.rbac import require_naas_role

JWT_SECRET = "integration-test-jwt-secret-32chars!"
MCP_PATH = "/mcp/"


# Override the session-scoped docker_compose autouse fixture from the integration conftest.
# This test module does not require Docker — it uses in-process ASGI testing.
@pytest.fixture(scope="session", autouse=True)
def docker_compose():
    """No-op override: HTTP transport tests don't need Docker."""
    yield


def _make_token(
    sub: str = "k-test",
    role: str = "operator",
    contexts: list[str] | None = None,
    secret: str = JWT_SECRET,
) -> str:
    """Create a valid JWT token for testing."""
    payload = {
        "sub": sub,
        "role": role,
        "contexts": contexts or ["*"],
        "iat": int(time.time()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _build_server() -> FastMCP:
    """Build a FastMCP server with JWT auth enabled (no Redis revocation)."""

    @asynccontextmanager
    async def test_lifespan(server: Any):
        mock_client = AsyncMock()
        mock_client.healthcheck.return_value = {"status": "healthy", "components": {}}
        yield {
            "client": mock_client,
            "job_poll_interval": 0.1,
            "job_timeout": 5.0,
            "transport": "streamable-http",
            "api_url": "http://mock-naas:8080",
            "timeout": 5.0,
        }

    auth_provider = NaasAuthProvider(jwt_secret=JWT_SECRET, redis_url=None)

    from fastmcp.server.middleware.authorization import AuthMiddleware

    middleware = AuthMiddleware(auth=require_naas_role)

    server = FastMCP(
        name="naas-http-test",
        lifespan=test_lifespan,
        auth=auth_provider,
        middleware=[middleware],
    )

    # Register tools and resources
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

    for fn in (
        send_command,
        send_command_structured,
        send_config,
        get_job_result,
        cancel_job,
        list_jobs,
        create_api_key,
        revoke_api_key,
    ):
        server.add_tool(fn)

    server.resource("naas://health", name="Health")(health)
    server.resource("naas://contexts", name="Contexts")(contexts)
    server.resource("naas://jobs/failed", name="Failed Jobs")(failed_jobs)
    server.resource("naas://jobs", name="Jobs")(jobs)

    return server


@asynccontextmanager
async def _managed_asgi_app(mcp_server: FastMCP):
    """Context manager that creates an ASGI app with active lifespan.

    The StreamableHTTP session manager requires the Starlette lifespan to be
    running. This helper starts the ASGI lifespan in a background task, yields
    the app, then shuts it down cleanly.
    """
    app = mcp_server.http_app(path=MCP_PATH, transport="streamable-http")

    # Drive the ASGI lifespan protocol manually
    startup_complete = asyncio.Event()
    shutdown_trigger = asyncio.Event()

    async def receive():
        if not startup_complete.is_set():
            startup_complete.set()
            return {"type": "lifespan.startup"}
        await shutdown_trigger.wait()
        return {"type": "lifespan.shutdown"}

    async def send(msg):
        if msg["type"] == "lifespan.startup.complete":
            startup_complete.set()

    lifespan_task = asyncio.create_task(app({"type": "lifespan", "asgi": {"version": "3.0"}}, receive, send))
    # Wait for lifespan startup to complete
    await asyncio.sleep(0.1)

    try:
        yield app
    finally:
        shutdown_trigger.set()
        await lifespan_task


@pytest.fixture
def mcp_server() -> FastMCP:
    """FastMCP server instance with HTTP auth configured."""
    return _build_server()


@pytest.fixture
def valid_token() -> str:
    """A valid JWT operator token."""
    return _make_token()


@pytest.fixture
def admin_token() -> str:
    """A valid JWT admin token."""
    return _make_token(sub="k-admin", role="admin")


# ---------------------------------------------------------------------------
# Tests: HTTP-level auth validation
# ---------------------------------------------------------------------------


async def test_missing_bearer_token_rejected(mcp_server: FastMCP):
    """Requests without a Bearer token should be rejected with 401."""
    async with (
        _managed_asgi_app(mcp_server) as app,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        resp = await client.post(
            MCP_PATH,
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {}},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


async def test_invalid_bearer_token_rejected(mcp_server: FastMCP):
    """Requests with an invalid (badly signed) Bearer token should be rejected with 401."""
    bad_token = jwt.encode(
        {"sub": "hacker", "role": "admin", "contexts": ["*"], "iat": int(time.time())},
        "wrong-secret-key-not-the-real-one!!",
        algorithm="HS256",
    )
    async with (
        _managed_asgi_app(mcp_server) as app,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        resp = await client.post(
            MCP_PATH,
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {}},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {bad_token}",
            },
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


async def test_valid_bearer_token_accepted(mcp_server: FastMCP, valid_token: str):
    """Requests with a valid Bearer token should be accepted (HTTP 200)."""
    async with (
        _managed_asgi_app(mcp_server) as app,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        resp = await client.post(
            MCP_PATH,
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {valid_token}",
            },
        )
        # Server should accept the connection — 200 with SSE or JSON response
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Tests: Full MCP client flow with Bearer auth over HTTP
# ---------------------------------------------------------------------------


async def test_mcp_client_with_bearer_auth(mcp_server: FastMCP, valid_token: str):
    """FastMCP Client connects successfully with Bearer auth via HTTP transport."""
    async with _managed_asgi_app(mcp_server) as app:

        def httpx_factory(**kwargs: Any) -> httpx.AsyncClient:
            """Create httpx client using ASGI transport for in-process testing."""
            return httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
                **{k: v for k, v in kwargs.items() if k not in ("base_url", "transport")},
            )

        transport = StreamableHttpTransport(
            url=f"http://testserver{MCP_PATH}",
            auth=BearerAuth(token=valid_token),
            httpx_client_factory=httpx_factory,
        )

        async with Client(transport=transport) as client:
            # Connection accepted — list tools to verify full MCP protocol works
            tools = await client.list_tools()
            assert len(tools) > 0, "Should have registered tools"

            # Verify expected tools are present
            tool_names = {t.name for t in tools}
            assert "send_command" in tool_names
            assert "list_jobs" in tool_names


async def test_mcp_client_invalid_token_fails(mcp_server: FastMCP):
    """FastMCP Client with invalid token should fail to connect."""
    bad_token = jwt.encode(
        {"sub": "hacker", "role": "admin", "contexts": ["*"], "iat": int(time.time())},
        "wrong-secret-key-not-the-real-one!!",
        algorithm="HS256",
    )
    async with _managed_asgi_app(mcp_server) as app:

        def httpx_factory(**kwargs: Any) -> httpx.AsyncClient:
            return httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
                **{k: v for k, v in kwargs.items() if k not in ("base_url", "transport")},
            )

        transport = StreamableHttpTransport(
            url=f"http://testserver{MCP_PATH}",
            auth=BearerAuth(token=bad_token),
            httpx_client_factory=httpx_factory,
        )

        with pytest.raises(Exception):  # noqa: B017  -- FastMCP raises varied exceptions for auth failures
            async with Client(transport=transport) as client:
                await client.list_tools()


async def test_mcp_client_no_token_fails(mcp_server: FastMCP):
    """FastMCP Client with no token should fail to connect."""
    async with _managed_asgi_app(mcp_server) as app:

        def httpx_factory(**kwargs: Any) -> httpx.AsyncClient:
            return httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
                **{k: v for k, v in kwargs.items() if k not in ("base_url", "transport")},
            )

        transport = StreamableHttpTransport(
            url=f"http://testserver{MCP_PATH}",
            httpx_client_factory=httpx_factory,
        )

        with pytest.raises(Exception):  # noqa: B017  -- FastMCP raises varied exceptions for auth failures
            async with Client(transport=transport) as client:
                await client.list_tools()


# ---------------------------------------------------------------------------
# Tests: Role-based access control via HTTP
# ---------------------------------------------------------------------------


async def test_viewer_role_can_list_tools(mcp_server: FastMCP):
    """A viewer-role token can connect and list tools (read operation)."""
    viewer_token = _make_token(sub="k-viewer", role="viewer")
    async with _managed_asgi_app(mcp_server) as app:

        def httpx_factory(**kwargs: Any) -> httpx.AsyncClient:
            return httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
                **{k: v for k, v in kwargs.items() if k not in ("base_url", "transport")},
            )

        transport = StreamableHttpTransport(
            url=f"http://testserver{MCP_PATH}",
            auth=BearerAuth(token=viewer_token),
            httpx_client_factory=httpx_factory,
        )

        async with Client(transport=transport) as client:
            tools = await client.list_tools()
            assert len(tools) > 0


async def test_admin_token_can_list_tools(mcp_server: FastMCP, admin_token: str):
    """An admin-role token can connect and list tools."""
    async with _managed_asgi_app(mcp_server) as app:

        def httpx_factory(**kwargs: Any) -> httpx.AsyncClient:
            return httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
                **{k: v for k, v in kwargs.items() if k not in ("base_url", "transport")},
            )

        transport = StreamableHttpTransport(
            url=f"http://testserver{MCP_PATH}",
            auth=BearerAuth(token=admin_token),
            httpx_client_factory=httpx_factory,
        )

        async with Client(transport=transport) as client:
            tools = await client.list_tools()
            assert len(tools) > 0
            tool_names = {t.name for t in tools}
            # Admin should see all tools
            assert "send_command" in tool_names
            assert "create_api_key" in tool_names
