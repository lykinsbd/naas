"""NAAS JWT authentication provider for FastMCP HTTP transport.

Validates NAAS API keys (JWTs signed with NAAS_JWT_SECRET) and checks
revocation against the shared Redis set. This allows the same API keys
to work for both direct NAAS API access and MCP access.
"""

from __future__ import annotations

import logging
import time

import jwt
from fastmcp.server.auth import AccessToken, TokenVerifier

logger = logging.getLogger(__name__)


class NaasAuthProvider(TokenVerifier):
    """Verify NAAS JWT API keys for MCP HTTP transport.

    Shares the same JWT secret and revocation store as the NAAS API server,
    so a single API key works for both direct API calls and MCP access.

    Args:
        jwt_secret: The NAAS_JWT_SECRET used to sign/verify API key JWTs.
        redis_url: Optional Redis URL for revocation checks. If None,
            revocation checking is skipped (tokens are validated by
            signature and expiry only).
    """

    def __init__(
        self,
        jwt_secret: str,
        redis_url: str | None = None,
    ) -> None:
        super().__init__()
        self._jwt_secret = jwt_secret
        self._redis_url = redis_url
        self._redis: object | None = None  # Lazy-initialized Redis connection

    def _get_redis(self):
        """Lazy-initialize Redis connection for revocation checks."""
        if self._redis is None and self._redis_url:
            from redis import Redis

            self._redis = Redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a NAAS JWT API key.

        Decodes the JWT, checks expiry, and optionally checks revocation
        against the Redis revoked_keys set.

        Args:
            token: The Bearer token (NAAS JWT API key).

        Returns:
            AccessToken with claims if valid, None if invalid/expired/revoked.
        """
        try:
            claims: dict = jwt.decode(token, self._jwt_secret, algorithms=["HS256"])
        except jwt.InvalidTokenError as exc:
            logger.debug("JWT validation failed: %s", exc)
            return None

        # Check revocation
        redis = self._get_redis()
        if redis is not None:
            key_id = claims.get("sub", "")
            if redis.sismember("naas:revoked_keys", key_id):
                logger.info("Rejected revoked API key: %s", key_id)
                return None

        # Build AccessToken for FastMCP
        return AccessToken(
            token=token,
            client_id=claims.get("sub", "unknown"),
            scopes=self._role_to_scopes(claims.get("role", "viewer")),
            expires_at=claims.get("exp"),
            claims=claims,
        )

    @staticmethod
    def _role_to_scopes(role: str) -> list[str]:
        """Map NAAS role to OAuth-style scopes for FastMCP compatibility.

        This allows using FastMCP's built-in scope checking if needed,
        but our primary RBAC uses the role claim directly.
        """
        scopes_map = {
            "viewer": ["read"],
            "operator": ["read", "execute"],
            "admin": ["read", "execute", "admin"],
        }
        return scopes_map.get(role, ["read"])
