"""RBAC authorization for NAAS MCP tools and resources.

Maps MCP components to minimum required NAAS roles and provides
an auth check callable compatible with FastMCP's AuthMiddleware.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp.server.auth import AccessToken
    from fastmcp.server.middleware.authorization import AuthContext

logger = logging.getLogger(__name__)

# NAAS role hierarchy (higher rank = more permissions)
ROLE_RANK: dict[str, int] = {"viewer": 0, "operator": 1, "admin": 2}

# MCP tool/resource → minimum required role
COMPONENT_ROLES: dict[str, str] = {
    # Tools requiring operator (execute on devices / modify state)
    "send_command": "operator",
    "send_command_structured": "operator",
    "send_config": "operator",
    "cancel_job": "operator",
    # Tools requiring viewer (read-only)
    "get_job": "viewer",
    "list_jobs": "viewer",
    # Resources (all read-only)
    "naas://health": "viewer",
    "naas://contexts": "viewer",
    "naas://failed-jobs": "viewer",
}


def require_naas_role(ctx: AuthContext) -> bool:
    """FastMCP auth check: enforce NAAS RBAC on MCP components.

    Used with FastMCP's AuthMiddleware to check if the authenticated
    user's role is sufficient for the requested tool/resource.

    Args:
        ctx: FastMCP AuthContext with the current token and component.

    Returns:
        True if authorized, False if insufficient role.
    """
    token: AccessToken | None = ctx.token
    if token is None:
        # No token = unauthenticated (should not happen if auth provider is configured)
        return False

    # Get user's role from JWT claims
    user_role = token.claims.get("role", "viewer")
    user_rank = ROLE_RANK.get(user_role, 0)

    # Determine the component name for lookup
    component_name = ctx.component.name if ctx.component else ""

    # Look up required role for this component
    required_role = COMPONENT_ROLES.get(component_name, "viewer")
    required_rank = ROLE_RANK.get(required_role, 0)

    if user_rank < required_rank:
        logger.info(
            "RBAC denied: key=%s role=%s attempted %s (requires %s)",
            token.client_id,
            user_role,
            component_name,
            required_role,
        )
        return False

    return True
