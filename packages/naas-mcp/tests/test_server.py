"""Unit tests for server configuration and structure."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from naas_mcp.server import _get_config

if TYPE_CHECKING:
    from fastmcp.client import Client


def test_default_config():
    with patch.dict(os.environ, {}, clear=True):
        cfg = _get_config()

    assert cfg["api_url"] == "http://localhost:8080"
    assert cfg["api_key"] == ""
    assert cfg["timeout"] == 30.0
    assert cfg["job_poll_interval"] == 2.0
    assert cfg["job_timeout"] == 300.0
    assert cfg["transport"] == "stdio"
    assert cfg["jwt_secret"] == ""
    assert cfg["redis_url"] == ""


def test_config_from_env():
    env = {
        "NAAS_MCP_API_URL": "https://naas.example.com",
        "NAAS_MCP_API_KEY": "test-key-123",
        "NAAS_MCP_TIMEOUT": "60",
        "NAAS_MCP_JOB_POLL_INTERVAL": "5",
        "NAAS_MCP_JOB_TIMEOUT": "600",
    }
    with patch.dict(os.environ, env, clear=True):
        cfg = _get_config()

    assert cfg["api_url"] == "https://naas.example.com"
    assert cfg["api_key"] == "test-key-123"
    assert cfg["timeout"] == 60.0
    assert cfg["job_poll_interval"] == 5.0
    assert cfg["job_timeout"] == 600.0


async def test_server_lists_all_tools(mcp_client: Client):
    tools = await mcp_client.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {
        "send_command",
        "send_command_structured",
        "send_config",
        "get_job_result",
        "cancel_job",
        "list_jobs",
        "create_api_key",
        "revoke_api_key",
    }


async def test_server_lists_all_resources(mcp_client: Client):
    resources = await mcp_client.list_resources()
    resource_uris = {str(r.uri) for r in resources}
    assert resource_uris == {"naas://health", "naas://contexts", "naas://jobs/failed", "naas://jobs"}


def test_main_entry_point_exists():
    from naas_mcp import main

    assert callable(main)


async def test_app_lifespan_creates_and_closes_client():
    """Test the real lifespan creates an AsyncNaasClient and closes it."""
    mock_instance = AsyncMock()

    with (
        patch("naas_mcp.server.AsyncNaasClient", return_value=mock_instance),
        patch(
            "naas_mcp.server._get_config",
            return_value={
                "api_url": "http://test:8080",
                "api_key": "key123",
                "timeout": 10.0,
                "job_poll_interval": 1.0,
                "job_timeout": 60.0,
                "transport": "stdio",
                "jwt_secret": "",
                "redis_url": "",
            },
        ),
    ):
        from naas_mcp.server import app_lifespan

        # Use the underlying async generator function directly
        @asynccontextmanager
        async def _wrap(server):
            async for ctx in app_lifespan._fn(server):
                yield ctx

        async with _wrap(None) as ctx:
            assert ctx["client"] is mock_instance
            assert ctx["job_poll_interval"] == 1.0
            assert ctx["job_timeout"] == 60.0
            assert ctx["transport"] == "stdio"

        mock_instance.close.assert_called_once()


def test_main_imports_and_calls_run():
    """Test that main() calls mcp.run() in stdio mode."""
    import sys

    with (
        patch("naas_mcp.server.mcp") as mock_mcp,
        patch.object(sys, "argv", ["naas-mcp"]),
        patch.dict(os.environ, {"NAAS_MCP_TRANSPORT": "stdio"}, clear=False),
    ):
        from naas_mcp import main

        main()
        mock_mcp.run.assert_called_once()


def test_get_auth_provider_stdio_returns_none():
    """In stdio mode, _get_auth_provider returns None."""
    with patch.dict(os.environ, {"NAAS_MCP_TRANSPORT": "stdio"}, clear=False):
        from naas_mcp.server import _get_auth_provider

        assert _get_auth_provider() is None


def test_get_auth_provider_http_requires_jwt_secret():
    """In HTTP mode without NAAS_JWT_SECRET, _get_auth_provider raises RuntimeError."""
    import pytest

    with patch.dict(
        os.environ,
        {"NAAS_MCP_TRANSPORT": "streamable-http", "NAAS_JWT_SECRET": "", "NAAS_MCP_REDIS_URL": ""},
        clear=False,
    ):
        from naas_mcp.server import _get_auth_provider

        with pytest.raises(RuntimeError, match="NAAS_JWT_SECRET is required"):
            _get_auth_provider()


def test_get_auth_provider_http_returns_provider():
    """In HTTP mode with NAAS_JWT_SECRET, _get_auth_provider returns NaasAuthProvider."""
    with patch.dict(
        os.environ,
        {
            "NAAS_MCP_TRANSPORT": "streamable-http",
            "NAAS_JWT_SECRET": "test-secret-32-chars-long-enough!",
            "NAAS_MCP_REDIS_URL": "",
        },
        clear=False,
    ):
        from naas_mcp.auth import NaasAuthProvider
        from naas_mcp.server import _get_auth_provider

        provider = _get_auth_provider()
        assert isinstance(provider, NaasAuthProvider)


def test_get_middleware_stdio_returns_none():
    """In stdio mode, _get_middleware returns None."""
    with patch.dict(os.environ, {"NAAS_MCP_TRANSPORT": "stdio"}, clear=False):
        from naas_mcp.server import _get_middleware

        assert _get_middleware() is None


def test_get_middleware_http_returns_auth_middleware():
    """In HTTP mode, _get_middleware returns AuthMiddleware."""
    with patch.dict(os.environ, {"NAAS_MCP_TRANSPORT": "streamable-http"}, clear=False):
        from fastmcp.server.middleware.authorization import AuthMiddleware

        from naas_mcp.server import _get_middleware

        middleware = _get_middleware()
        assert isinstance(middleware, AuthMiddleware)


def test_main_http_mode():
    """Test that main() calls mcp.run with streamable-http transport."""
    import sys

    with (
        patch("naas_mcp.server.mcp") as mock_mcp,
        patch.object(sys, "argv", ["naas-mcp", "--transport", "streamable-http", "--port", "9090"]),
        patch.dict(os.environ, {"NAAS_JWT_SECRET": "test-secret-32-chars-long-enough!"}, clear=False),
    ):
        from naas_mcp import main

        main()
        mock_mcp.run.assert_called_once_with(transport="streamable-http", port=9090)


def test_client_http_mode_uses_access_token():
    """In HTTP mode, _client creates a per-request client with the caller's token."""
    from unittest.mock import MagicMock, patch

    from fastmcp.server.auth import AccessToken

    mock_ctx = MagicMock()
    mock_ctx.lifespan_context = {
        "transport": "streamable-http",
        "api_url": "http://naas-api:8080",
        "timeout": 30.0,
        "client": MagicMock(),
    }

    mock_token = AccessToken(
        token="eyJ-test-token",
        client_id="k-test",
        scopes=["read", "execute"],
        claims={"role": "operator", "sub": "k-test"},
    )

    with (
        patch("naas_mcp.tools.get_access_token", return_value=mock_token),
        patch("naas_mcp.tools.AsyncNaasClient") as mock_client_cls,
    ):
        from naas_mcp.tools import _client

        _client(mock_ctx)
        mock_client_cls.assert_called_once_with(
            base_url="http://naas-api:8080",
            api_key="eyJ-test-token",
            timeout=30.0,
        )


def test_client_stdio_mode_uses_lifespan_client():
    """In stdio mode, _client returns the shared lifespan client."""
    from unittest.mock import MagicMock

    mock_shared_client = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.lifespan_context = {
        "transport": "stdio",
        "client": mock_shared_client,
    }

    from naas_mcp.tools import _client

    result = _client(mock_ctx)
    assert result is mock_shared_client


def test_client_http_mode_fallback_no_token():
    """In HTTP mode with no access token, _client falls back to shared client."""
    from unittest.mock import MagicMock, patch

    mock_shared_client = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.lifespan_context = {
        "transport": "streamable-http",
        "api_url": "http://naas-api:8080",
        "timeout": 30.0,
        "client": mock_shared_client,
    }

    with patch("naas_mcp.tools.get_access_token", return_value=None):
        from naas_mcp.tools import _client

        result = _client(mock_ctx)
        assert result is mock_shared_client
