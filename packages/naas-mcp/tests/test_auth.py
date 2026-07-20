"""Unit tests for NAAS auth provider and RBAC."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import jwt
import pytest

from naas_mcp.auth import NaasAuthProvider
from naas_mcp.rbac import require_naas_role

JWT_SECRET = "test-secret-for-unit-tests"


def _make_token(
    sub: str = "k-test123",
    role: str = "operator",
    contexts: list[str] | None = None,
    exp: int | None = None,
) -> str:
    """Create a test JWT token."""
    claims = {"sub": sub, "role": role, "contexts": contexts or ["*"], "iat": int(time.time())}
    if exp is not None:
        claims["exp"] = exp
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")


class TestNaasAuthProvider:
    """Tests for NaasAuthProvider JWT validation."""

    @pytest.fixture
    def provider(self) -> NaasAuthProvider:
        return NaasAuthProvider(jwt_secret=JWT_SECRET, redis_url=None)

    @pytest.fixture
    def provider_with_redis(self) -> NaasAuthProvider:
        provider = NaasAuthProvider(jwt_secret=JWT_SECRET, redis_url="redis://localhost:6379/0")
        # Mock the Redis connection
        mock_redis = MagicMock()
        provider._redis = mock_redis
        return provider

    @pytest.mark.asyncio
    async def test_valid_token(self, provider: NaasAuthProvider):
        """Valid JWT returns AccessToken with correct claims."""
        token = _make_token(sub="k-abc123", role="admin")
        result = await provider.verify_token(token)

        assert result is not None
        assert result.client_id == "k-abc123"
        assert result.token == token
        assert result.claims["role"] == "admin"
        assert result.claims["sub"] == "k-abc123"
        assert "read" in result.scopes
        assert "execute" in result.scopes
        assert "admin" in result.scopes

    @pytest.mark.asyncio
    async def test_expired_token(self, provider: NaasAuthProvider):
        """Expired JWT returns None."""
        token = _make_token(exp=int(time.time()) - 3600)
        result = await provider.verify_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_signature(self, provider: NaasAuthProvider):
        """Token signed with wrong secret returns None."""
        token = jwt.encode({"sub": "k-bad", "role": "admin"}, "wrong-secret", algorithm="HS256")
        result = await provider.verify_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_token(self, provider: NaasAuthProvider):
        """Garbage token returns None."""
        result = await provider.verify_token("not.a.valid.jwt.at.all")
        assert result is None

    @pytest.mark.asyncio
    async def test_revoked_token(self, provider_with_redis: NaasAuthProvider):
        """Revoked token (in Redis set) returns None."""
        provider_with_redis._redis.sismember.return_value = True  # type: ignore[union-attr]
        token = _make_token(sub="k-revoked")
        result = await provider_with_redis.verify_token(token)
        assert result is None
        provider_with_redis._redis.sismember.assert_called_once_with("naas:revoked_keys", "k-revoked")  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_non_revoked_token(self, provider_with_redis: NaasAuthProvider):
        """Non-revoked token passes revocation check."""
        provider_with_redis._redis.sismember.return_value = False  # type: ignore[union-attr]
        token = _make_token(sub="k-valid")
        result = await provider_with_redis.verify_token(token)
        assert result is not None
        assert result.client_id == "k-valid"

    @pytest.mark.asyncio
    async def test_role_to_scopes_viewer(self, provider: NaasAuthProvider):
        """Viewer role maps to read scope only."""
        token = _make_token(role="viewer")
        result = await provider.verify_token(token)
        assert result is not None
        assert result.scopes == ["read"]

    @pytest.mark.asyncio
    async def test_role_to_scopes_operator(self, provider: NaasAuthProvider):
        """Operator role maps to read + execute scopes."""
        token = _make_token(role="operator")
        result = await provider.verify_token(token)
        assert result is not None
        assert result.scopes == ["read", "execute"]

    @pytest.mark.asyncio
    async def test_no_redis_skips_revocation(self, provider: NaasAuthProvider):
        """When redis_url is None, revocation check is skipped."""
        token = _make_token(sub="k-any")
        result = await provider.verify_token(token)
        # Should succeed without any Redis interaction
        assert result is not None


class TestRBAC:
    """Tests for require_naas_role auth check."""

    def _make_auth_context(self, role: str, component_name: str):
        """Create a mock AuthContext for testing."""
        from fastmcp.server.auth import AccessToken
        from fastmcp.server.middleware.authorization import AuthContext

        token = AccessToken(
            token="test",
            client_id="k-test",
            scopes=[],
            claims={"role": role, "sub": "k-test"},
        )
        component = MagicMock()
        component.name = component_name
        return AuthContext(token=token, component=component)

    def test_operator_can_send_command(self):
        """Operator role can access send_command."""
        ctx = self._make_auth_context("operator", "send_command")
        assert require_naas_role(ctx) is True

    def test_viewer_cannot_send_command(self):
        """Viewer role is denied send_command (requires operator)."""
        ctx = self._make_auth_context("viewer", "send_command")
        assert require_naas_role(ctx) is False

    def test_viewer_can_list_jobs(self):
        """Viewer role can access list_jobs (read-only)."""
        ctx = self._make_auth_context("viewer", "list_jobs")
        assert require_naas_role(ctx) is True

    def test_viewer_cannot_cancel_job(self):
        """Viewer role is denied cancel_job (requires operator)."""
        ctx = self._make_auth_context("viewer", "cancel_job")
        assert require_naas_role(ctx) is False

    def test_admin_can_do_everything(self):
        """Admin role can access all tools."""
        for component in ["send_command", "send_config", "cancel_job", "list_jobs", "get_job"]:
            ctx = self._make_auth_context("admin", component)
            assert require_naas_role(ctx) is True, f"Admin should access {component}"

    def test_no_token_is_denied(self):
        """Missing token (None) is denied."""
        from fastmcp.server.middleware.authorization import AuthContext

        component = MagicMock()
        component.name = "send_command"
        ctx = AuthContext(token=None, component=component)
        assert require_naas_role(ctx) is False

    def test_unknown_component_defaults_to_viewer(self):
        """Components not in COMPONENT_ROLES default to viewer-accessible."""
        ctx = self._make_auth_context("viewer", "some_unknown_tool")
        assert require_naas_role(ctx) is True
